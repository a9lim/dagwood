"""Pure graph algorithms — hand-rolled, no networkx.

Edge convention: `node.needs` are prerequisites. Following a `needs` edge goes
from a dependent to the thing it depends on. Topological order returns
prerequisites before the nodes that need them.
"""

from __future__ import annotations

import heapq
from collections.abc import Iterator

from .errors import CycleError
from .model import Graph


def detect_cycle(g: Graph) -> list[str] | None:
    """Return a cycle as a list of ids (closed, e.g. ['a','b','a']), or None.

    Iterative three-colour DFS over `needs` edges so deep graphs don't blow the
    recursion limit.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {nid: WHITE for nid in g.nodes}

    for root in g.nodes:
        if color[root] != WHITE:
            continue
        color[root] = GRAY
        stack: list[tuple[str, Iterator[str]]] = [(root, iter(g.nodes[root].needs))]
        while stack:
            node, it = stack[-1]
            advanced = False
            for nxt in it:
                if nxt not in g.nodes:
                    continue
                c = color[nxt]
                if c == GRAY:
                    ids = [sn for sn, _ in stack]
                    i = ids.index(nxt)
                    return ids[i:] + [nxt]
                if c == WHITE:
                    color[nxt] = GRAY
                    stack.append((nxt, iter(g.nodes[nxt].needs)))
                    advanced = True
                    break
                # BLACK: fully explored, skip.
            if not advanced:
                color[node] = BLACK
                stack.pop()
    return None


def topo_sort(g: Graph) -> list[str]:
    """Kahn's algorithm; prerequisites before dependents.

    Ties are broken lexicographically by id so the order is canonical regardless
    of dict insertion order. Raises CycleError if the graph is cyclic.
    """
    indeg: dict[str, int] = {nid: 0 for nid in g.nodes}
    dependents: dict[str, list[str]] = {nid: [] for nid in g.nodes}
    for nid, node in g.nodes.items():
        for dep in node.needs:
            if dep in g.nodes:
                indeg[nid] += 1
                dependents[dep].append(nid)

    heap: list[str] = [nid for nid, d in indeg.items() if d == 0]
    heapq.heapify(heap)
    order: list[str] = []
    while heap:
        nid = heapq.heappop(heap)
        order.append(nid)
        for m in dependents[nid]:
            indeg[m] -= 1
            if indeg[m] == 0:
                heapq.heappush(heap, m)

    if len(order) != len(g.nodes):
        raise CycleError(detect_cycle(g) or [])
    return order


def is_ready(g: Graph, nid: str) -> bool:
    node = g.node(nid)
    if node.status == "done":
        return False
    return all(g.nodes[d].status == "done" for d in node.needs if d in g.nodes)


def is_blocked(g: Graph, nid: str) -> bool:
    node = g.node(nid)
    if node.status == "done":
        return False
    return any(g.nodes[d].status != "done" for d in node.needs if d in g.nodes)


def frontier(g: Graph) -> list[str]:
    """Not-done nodes whose every prerequisite is done — what's actionable now."""
    return [nid for nid in topo_sort(g) if is_ready(g, nid)]


def blocked_nodes(g: Graph) -> list[str]:
    return [nid for nid in topo_sort(g) if is_blocked(g, nid)]


def why_blocked(g: Graph, nid: str) -> list[str]:
    """The unmet (not-done) prerequisites of `nid`."""
    node = g.node(nid)
    return [d for d in node.needs if d in g.nodes and g.nodes[d].status != "done"]


def critical_path(g: Graph) -> list[str]:
    """Longest dependency chain (by node count), prerequisite → final. Optional."""
    if not g.nodes:
        return []
    order = topo_sort(g)
    best_len: dict[str, int] = {nid: 1 for nid in g.nodes}
    best_prev: dict[str, str | None] = {nid: None for nid in g.nodes}
    for nid in order:
        for dep in g.nodes[nid].needs:
            if dep in g.nodes and best_len[dep] + 1 > best_len[nid]:
                best_len[nid] = best_len[dep] + 1
                best_prev[nid] = dep
    end = max(g.nodes, key=lambda nid: (best_len[nid], nid))
    path: list[str] = []
    cur: str | None = end
    while cur is not None:
        path.append(cur)
        cur = best_prev[cur]
    path.reverse()
    return path
