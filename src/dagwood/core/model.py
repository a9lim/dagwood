"""Core data model: Node and Graph.

A Node is immutable (frozen); mutations in graph.py produce new Graph values.
`ready` / `blocked` / `frontier` are never stored here — they're derived in
algos.py from `status` + `needs`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .errors import NodeNotFound

Status = Literal["todo", "doing", "done"]
STATUSES: frozenset[str] = frozenset(("todo", "doing", "done"))


@dataclass(frozen=True, slots=True)
class Node:
    id: str
    title: str
    status: Status = "todo"
    notes: str = ""
    # `needs` lists this node's prerequisites (depends-on edges). Edge a->b
    # ("a must finish before b") is stored as b.needs containing "a".
    needs: tuple[str, ...] = ()
    created: str | None = None
    updated: str | None = None


def _empty_nodes() -> dict[str, Node]:
    return {}


def _empty_meta() -> dict[str, str]:
    return {}


@dataclass(slots=True)
class Graph:
    nodes: dict[str, Node] = field(default_factory=_empty_nodes)
    meta: dict[str, str] = field(default_factory=_empty_meta)

    def node(self, nid: str) -> Node:
        try:
            return self.nodes[nid]
        except KeyError:
            raise NodeNotFound(nid) from None

    def __contains__(self, nid: object) -> bool:
        return nid in self.nodes
