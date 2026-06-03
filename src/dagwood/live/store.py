"""The authoritative in-memory store — and the SOLE writer of dag.toml.

All mutation logic here is synchronous, which (in asyncio's single-threaded
loop) makes each mutation atomic with respect to concurrent websocket handlers:
no lock needed, no interleaving. The server is the only writer, so the
canvas, the MCP layer, and the CLI all funnel through `apply_mutation`.
"""

from __future__ import annotations

import asyncio
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from .. import oplog
from ..core import graph as gops
from ..core import toml_io
from ..core.errors import CycleError, DagError, NodeNotFound, ValidationError
from ..core.model import Graph
from . import protocol
from .layout import load_layout, save_layout


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class MutationError(Exception):
    """A client mutation was rejected. `code` is a stable machine token."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _req_str(data: Any, key: str) -> str:
    try:
        v = data.get(key)
    except AttributeError as e:
        raise MutationError("bad_request", "message must be an object") from e
    if not isinstance(v, str) or not v:
        raise MutationError("bad_request", f"missing or invalid {key!r}")
    return v


def _opt_str(data: Any, key: str) -> str | None:
    v = data.get(key)
    if v is None:
        return None
    if not isinstance(v, str):
        raise MutationError("bad_request", f"{key!r} must be a string")
    return v


def _opt_str_list(data: Any, key: str) -> list[str]:
    v = data.get(key, [])
    if v is None:
        return []
    if not isinstance(v, list):
        raise MutationError("bad_request", f"{key!r} must be a list of ids")
    out: list[str] = []
    for x in cast("list[Any]", v):
        if not isinstance(x, str):
            raise MutationError("bad_request", f"{key!r} must contain only string ids")
        out.append(x)
    return out


def _req_num(data: Any, key: str) -> float:
    v = data.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise MutationError("bad_request", f"missing or invalid number {key!r}")
    return float(v)


class Store:
    def __init__(self, dag_path: str | Path, layout_path: str | Path) -> None:
        self.dag_path = Path(dag_path)
        self.layout_path = Path(layout_path)
        self.ops_path = self.dag_path.parent / "ops.jsonl"
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        if self.dag_path.exists():
            self.graph = toml_io.load_toml(self.dag_path)
            self._last_written: str | None = self.dag_path.read_text(encoding="utf-8")
        else:
            self.graph = Graph()
            self._last_written = None
        self.layout = load_layout(self.layout_path)

    # --- subscriptions -------------------------------------------------------
    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(q)

    def broadcast(self, msg: dict[str, Any]) -> None:
        for q in list(self._subscribers):
            q.put_nowait(msg)

    def snapshot(self) -> dict[str, Any]:
        return protocol.snapshot_msg(self.graph)

    # --- graph mutation (sole writer) ---------------------------------------
    def _save(self) -> None:
        text = toml_io.dump_toml(self.graph)
        toml_io.atomic_write_text(self.dag_path, text)
        self._last_written = text

    def _apply_to_graph(self, data: Any, now: str) -> Graph:
        t = data.get("type") if hasattr(data, "get") else None
        if t == "add_node":
            g, _ = gops.add_node(
                self.graph,
                _req_str(data, "title"),
                status=_opt_str(data, "status") or "todo",
                notes=_opt_str(data, "notes") or "",
                needs=_opt_str_list(data, "needs"),
                now=now,
            )
            return g
        if t == "set_status":
            return gops.set_status(self.graph, _req_str(data, "id"), _req_str(data, "status"), now=now)
        if t == "set_fields":
            return gops.set_fields(
                self.graph,
                _req_str(data, "id"),
                title=_opt_str(data, "title"),
                notes=_opt_str(data, "notes"),
                now=now,
            )
        if t == "add_edge":
            return gops.add_edge(self.graph, _req_str(data, "src"), _req_str(data, "dst"), now=now)
        if t == "remove_edge":
            return gops.remove_edge(self.graph, _req_str(data, "src"), _req_str(data, "dst"), now=now)
        if t == "remove_node":
            return gops.remove_node(self.graph, _req_str(data, "id"))
        raise MutationError("bad_request", f"unknown mutation type: {t!r}")

    def apply_mutation(
        self,
        data: Any,
        now: str | None = None,
        op_id: str | None = None,
        source: str = "server",
    ) -> dict[str, Any]:
        now = now or now_iso()
        try:
            newg = self._apply_to_graph(data, now)
        except CycleError as e:
            raise MutationError("cycle", str(e)) from e
        except NodeNotFound as e:
            raise MutationError("not_found", str(e)) from e
        except ValidationError as e:
            raise MutationError("validation", str(e)) from e

        old, new = self.graph.nodes, newg.nodes
        added = [protocol.node_to_dict(new[i]) for i in new if i not in old]
        removed = [i for i in old if i not in new]
        updated = [protocol.node_to_dict(new[i]) for i in new if i in old and new[i] != old[i]]

        self.graph = newg
        self._save()
        op = data.get("type") if hasattr(data, "get") else None
        oplog.append(
            self.ops_path,
            {
                "ts": now,
                "source": source,
                "op": op,
                "op_id": op_id,
                "added": [n["id"] for n in added],
                "updated": [n["id"] for n in updated],
                "removed": removed,
            },
        )
        return protocol.patch_msg(self.graph, added, updated, removed, op_id=op_id)

    # --- external edits ------------------------------------------------------
    def reload_if_external(self) -> dict[str, Any] | None:
        """Called by the watcher. Returns a message to broadcast, or None if the
        change was our own write (suppressed) or the file vanished."""
        try:
            text = self.dag_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        if text == self._last_written:
            return None  # our own atomic write — suppress the echo
        try:
            self.graph = toml_io.loads(text)
        except (DagError, tomllib.TOMLDecodeError):
            return protocol.status_msg(False, "file")  # surface, don't adopt, don't crash
        self._last_written = text
        return protocol.snapshot_msg(self.graph)

    # --- layout (geometry sidecar; never touches dag.toml) ------------------
    def set_layout(self, nid: str, x: float, y: float) -> None:
        self.layout.overrides[nid] = {"x": x, "y": y}
        save_layout(self.layout_path, self.layout)

    def set_viewport(self, x: float, y: float, zoom: float) -> None:
        self.layout.viewport = {"x": x, "y": y, "zoom": zoom}
        save_layout(self.layout_path, self.layout)

    def handle_layout(self, data: Any) -> None:
        t = data.get("type") if hasattr(data, "get") else None
        if t == "set_layout":
            self.set_layout(_req_str(data, "id"), _req_num(data, "x"), _req_num(data, "y"))
        elif t == "set_viewport":
            self.set_viewport(_req_num(data, "x"), _req_num(data, "y"), _req_num(data, "zoom"))
        else:
            raise MutationError("bad_request", f"unknown layout type: {t!r}")
