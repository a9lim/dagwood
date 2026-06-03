"""Deterministic round-trip of the semantic source-of-truth file (.dag/dag.toml).

Read with stdlib tomllib; write with a hand-rolled serializer so output is
byte-stable (stable field order, canonical escaping) and git diffs stay clean.
No comment preservation is needed — the file is generated.
"""

from __future__ import annotations

import os
import tempfile
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from .algos import detect_cycle
from .errors import CycleError, DuplicateId, ValidationError
from .model import STATUSES, Graph, Node, Status

SCHEMA_VERSION = 1

# Stable serialization order for node fields.
_FIELD_ORDER = ("id", "title", "status", "needs", "notes", "created", "updated")

_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
    "\b": "\\b",
    "\f": "\\f",
}


def _basic(s: str) -> str:
    """Render a TOML single-line basic string with canonical escaping."""
    out: list[str] = []
    for ch in s:
        esc = _ESCAPES.get(ch)
        if esc is not None:
            out.append(esc)
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _array(items: Iterable[str]) -> str:
    items = list(items)
    if not items:
        return "[]"
    return "[" + ", ".join(_basic(x) for x in items) + "]"


def _coerce_ts(v: object) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    iso = getattr(v, "isoformat", None)
    if callable(iso):
        return cast(str, iso())
    raise ValidationError(f"timestamp must be a string, got {type(v).__name__}")


def _from_dict(data: dict[str, Any]) -> Graph:
    version = data.get("version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise ValidationError(f"unsupported schema version: {version!r} (expected {SCHEMA_VERSION})")

    meta_raw = data.get("meta", {})
    if not isinstance(meta_raw, dict):
        raise ValidationError("[meta] must be a table")
    meta = {str(k): str(v) for k, v in cast("dict[Any, Any]", meta_raw).items()}

    raw_nodes = data.get("node", [])
    if not isinstance(raw_nodes, list):
        raise ValidationError("[[node]] must be an array of tables")

    nodes: dict[str, Node] = {}
    for raw_item in cast("list[Any]", raw_nodes):
        if not isinstance(raw_item, dict):
            raise ValidationError(f"each node must be a table, got {type(raw_item).__name__}")
        raw = cast("dict[str, Any]", raw_item)
        nid = raw.get("id")
        if not isinstance(nid, str) or not nid:
            raise ValidationError(f"node missing a non-empty string id: {raw!r}")
        if nid in nodes:
            raise DuplicateId(nid)
        title = raw.get("title", "")
        if not isinstance(title, str):
            raise ValidationError(f"node {nid}: title must be a string")
        status = raw.get("status", "todo")
        if status not in STATUSES:
            raise ValidationError(f"node {nid}: invalid status {status!r}")
        notes = raw.get("notes", "")
        if not isinstance(notes, str):
            raise ValidationError(f"node {nid}: notes must be a string")
        needs_raw = raw.get("needs", [])
        if not isinstance(needs_raw, list) or not all(isinstance(x, str) for x in cast("list[Any]", needs_raw)):
            raise ValidationError(f"node {nid}: needs must be a list of ids")
        nodes[nid] = Node(
            id=nid,
            title=title,
            status=cast(Status, status),
            notes=notes,
            needs=tuple(cast("list[str]", needs_raw)),
            created=_coerce_ts(raw.get("created")),
            updated=_coerce_ts(raw.get("updated")),
        )

    for node in nodes.values():
        for dep in node.needs:
            if dep not in nodes:
                raise ValidationError(f"node {node.id}: needs unknown node {dep!r}")

    g = Graph(nodes=nodes, meta=meta)
    cyc = detect_cycle(g)
    if cyc:
        raise CycleError(cyc)
    return g


def loads(text: str) -> Graph:
    return _from_dict(tomllib.loads(text))


def load_toml(path: str | os.PathLike[str]) -> Graph:
    with Path(path).open("rb") as f:
        return _from_dict(tomllib.load(f))


def dumps(g: Graph) -> str:
    return dump_toml(g)


def dump_toml(g: Graph) -> str:
    lines: list[str] = [f"version = {SCHEMA_VERSION}"]

    if g.meta:
        lines.append("")
        lines.append("[meta]")
        for key in sorted(g.meta):
            lines.append(f"{key} = {_basic(g.meta[key])}")

    for node in g.nodes.values():
        lines.append("")
        lines.append("[[node]]")
        values: dict[str, str] = {
            "id": _basic(node.id),
            "title": _basic(node.title),
            "status": _basic(node.status),
            "needs": _array(node.needs),
        }
        if node.notes:
            values["notes"] = _basic(node.notes)
        if node.created is not None:
            values["created"] = _basic(node.created)
        if node.updated is not None:
            values["updated"] = _basic(node.updated)
        for field_name in _FIELD_ORDER:
            if field_name in values:
                lines.append(f"{field_name} = {values[field_name]}")

    return "\n".join(lines) + "\n"


def atomic_write_text(path: str | os.PathLike[str], text: str) -> None:
    """Write `text` to `path` atomically (tmp in same dir → fsync → os.replace)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=p.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_toml(path: str | os.PathLike[str], g: Graph) -> None:
    atomic_write_text(path, dump_toml(g))
