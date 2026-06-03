"""Wire format for HTTP/websocket messages. Mirror this in web/src/lib/protocol.ts.

Server -> client: snapshot | patch | error | status
Client -> server: mutations (add_node, set_status, set_fields, add_edge,
remove_edge, remove_node) and layout ops (set_layout, set_viewport), each
optionally carrying an `op_id` the server echoes back for correlation.
"""

from __future__ import annotations

from typing import Any

from ..core import algos
from ..core.model import Graph, Node


def node_to_dict(n: Node) -> dict[str, Any]:
    return {
        "id": n.id,
        "title": n.title,
        "status": n.status,
        "notes": n.notes,
        "needs": list(n.needs),
        "created": n.created,
        "updated": n.updated,
    }


def derived(g: Graph) -> dict[str, list[str]]:
    """Server-computed actionability so clients can tint without recomputing."""
    return {"frontier": algos.frontier(g), "blocked": algos.blocked_nodes(g)}


def snapshot_msg(g: Graph) -> dict[str, Any]:
    return {
        "type": "snapshot",
        "nodes": [node_to_dict(n) for n in g.nodes.values()],
        "meta": dict(g.meta),
        "derived": derived(g),
    }


def patch_msg(
    g: Graph,
    added: list[dict[str, Any]],
    updated: list[dict[str, Any]],
    removed: list[str],
    op_id: str | None = None,
) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "type": "patch",
        "added": added,
        "updated": updated,
        "removed": removed,
        "derived": derived(g),
    }
    if op_id is not None:
        msg["op_id"] = op_id
    return msg


def error_msg(code: str, message: str, op_id: str | None = None) -> dict[str, Any]:
    msg: dict[str, Any] = {"type": "error", "code": code, "message": message}
    if op_id is not None:
        msg["op_id"] = op_id
    return msg


def status_msg(parse_ok: bool, source: str) -> dict[str, Any]:
    return {"type": "status", "parse_ok": parse_ok, "source": source}
