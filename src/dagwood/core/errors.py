"""Engine error hierarchy. Pure — no imports outside the stdlib."""

from __future__ import annotations

from collections.abc import Sequence


class DagError(Exception):
    """Base class for all dagwood engine errors."""


class ValidationError(DagError):
    """A graph or file failed a structural/semantic invariant."""


class NodeNotFound(DagError):
    """Referenced a node id that doesn't exist in the graph."""

    def __init__(self, nid: str) -> None:
        self.nid = nid
        super().__init__(f"no such node: {nid!r}")


class DuplicateId(DagError):
    """Two nodes share an id."""

    def __init__(self, nid: str) -> None:
        self.nid = nid
        super().__init__(f"duplicate node id: {nid!r}")


class CycleError(DagError):
    """An operation would create (or a loaded file contains) a dependency cycle."""

    def __init__(self, cycle: Sequence[str]) -> None:
        self.cycle: list[str] = list(cycle)
        rendered = " -> ".join(self.cycle) if self.cycle else "<unknown>"
        super().__init__(f"dependency cycle: {rendered}")
