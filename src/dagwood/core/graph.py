"""Graph mutation API.

Every mutator returns a NEW Graph (Nodes are frozen; we copy-on-write the node
dict). Acyclicity is enforced in exactly two places in the engine: here (on
edge-creating mutations) and in toml_io.load_toml (on load). No other layer
re-implements the check.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from typing import cast

from .algos import detect_cycle
from .errors import CycleError, NodeNotFound, ValidationError
from .ids import new_id
from .model import STATUSES, Graph, Node, Status


def _with_nodes(g: Graph, nodes: dict[str, Node]) -> Graph:
    return Graph(nodes=nodes, meta=dict(g.meta))


def add_node(
    g: Graph,
    title: str,
    *,
    status: str = "todo",
    notes: str = "",
    needs: Iterable[str] = (),
    now: str | None = None,
) -> tuple[Graph, str]:
    if status not in STATUSES:
        raise ValidationError(f"invalid status: {status!r}")
    needs_t = tuple(needs)
    for dep in needs_t:
        if dep not in g.nodes:
            raise NodeNotFound(dep)
    nid = new_id(g.nodes)
    node = Node(
        id=nid,
        title=title,
        status=cast(Status, status),
        notes=notes,
        needs=needs_t,
        created=now,
        updated=now,
    )
    nodes = dict(g.nodes)
    nodes[nid] = node
    ng = _with_nodes(g, nodes)
    # A brand-new node has no dependents, so it can't close a cycle — but check
    # defensively to keep the invariant in one place.
    cyc = detect_cycle(ng)
    if cyc:
        raise CycleError(cyc)
    return ng, nid


def remove_node(g: Graph, nid: str) -> Graph:
    if nid not in g.nodes:
        raise NodeNotFound(nid)
    nodes: dict[str, Node] = {}
    for key, node in g.nodes.items():
        if key == nid:
            continue
        if nid in node.needs:
            nodes[key] = replace(node, needs=tuple(d for d in node.needs if d != nid))
        else:
            nodes[key] = node
    return _with_nodes(g, nodes)


def add_edge(g: Graph, src: str, dst: str, *, now: str | None = None) -> Graph:
    """Add depends-on edge src->dst (i.e. dst.needs gains src). Cycle-guarded."""
    if src not in g.nodes:
        raise NodeNotFound(src)
    if dst not in g.nodes:
        raise NodeNotFound(dst)
    if src == dst:
        raise ValidationError("a node cannot depend on itself")
    dnode = g.nodes[dst]
    if src in dnode.needs:
        return g  # idempotent
    new_dst = replace(dnode, needs=dnode.needs + (src,), updated=now if now is not None else dnode.updated)
    nodes = dict(g.nodes)
    nodes[dst] = new_dst
    ng = _with_nodes(g, nodes)
    cyc = detect_cycle(ng)
    if cyc:
        raise CycleError(cyc)
    return ng


def remove_edge(g: Graph, src: str, dst: str, *, now: str | None = None) -> Graph:
    if dst not in g.nodes:
        raise NodeNotFound(dst)
    dnode = g.nodes[dst]
    if src not in dnode.needs:
        return g  # idempotent
    new_dst = replace(
        dnode,
        needs=tuple(d for d in dnode.needs if d != src),
        updated=now if now is not None else dnode.updated,
    )
    nodes = dict(g.nodes)
    nodes[dst] = new_dst
    return _with_nodes(g, nodes)


def set_status(g: Graph, nid: str, status: str, *, now: str | None = None) -> Graph:
    if nid not in g.nodes:
        raise NodeNotFound(nid)
    if status not in STATUSES:
        raise ValidationError(f"invalid status: {status!r}")
    node = g.nodes[nid]
    new = replace(node, status=cast(Status, status), updated=now if now is not None else node.updated)
    nodes = dict(g.nodes)
    nodes[nid] = new
    return _with_nodes(g, nodes)


def set_fields(
    g: Graph,
    nid: str,
    *,
    title: str | None = None,
    notes: str | None = None,
    now: str | None = None,
) -> Graph:
    if nid not in g.nodes:
        raise NodeNotFound(nid)
    node = g.nodes[nid]
    changes: dict[str, object] = {}
    if title is not None:
        changes["title"] = title
    if notes is not None:
        changes["notes"] = notes
    if changes:
        changes["updated"] = now if now is not None else node.updated
    new = replace(node, **changes)
    nodes = dict(g.nodes)
    nodes[nid] = new
    return _with_nodes(g, nodes)
