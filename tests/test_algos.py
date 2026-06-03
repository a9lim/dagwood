import pytest

from dagwood.core import algos
from dagwood.core.errors import CycleError
from dagwood.core.model import Graph, Node


def mk(*nodes: Node) -> Graph:
    return Graph(nodes={n.id: n for n in nodes})


def N(i: str, status: str = "todo", needs: tuple[str, ...] = ()) -> Node:
    return Node(id=i, title=i.upper(), status=status, needs=tuple(needs))  # type: ignore[arg-type]


def test_topo_chain():
    g = mk(N("a"), N("b", needs=("a",)), N("c", needs=("b",)))
    assert algos.topo_sort(g) == ["a", "b", "c"]


def test_topo_tiebreak_lexicographic():
    g = mk(N("b"), N("a"), N("c", needs=("a", "b")))
    assert algos.topo_sort(g) == ["a", "b", "c"]


def test_frontier_and_blocked():
    g = mk(N("a"), N("b", needs=("a",)), N("c", needs=("b",)))
    assert algos.frontier(g) == ["a"]
    assert algos.blocked_nodes(g) == ["b", "c"]

    g2 = mk(N("a", status="done"), N("b", needs=("a",)), N("c", needs=("b",)))
    assert algos.frontier(g2) == ["b"]
    assert algos.is_ready(g2, "b")
    assert not algos.is_ready(g2, "c")
    assert algos.is_blocked(g2, "c")


def test_done_excluded_from_frontier():
    g = mk(N("a", status="done"))
    assert algos.frontier(g) == []


def test_why_blocked():
    g = mk(N("a"), N("b", status="done"), N("c", needs=("a", "b")))
    assert algos.why_blocked(g, "c") == ["a"]


def test_detect_cycle():
    g = mk(N("a", needs=("b",)), N("b", needs=("a",)))
    cyc = algos.detect_cycle(g)
    assert cyc is not None
    assert cyc[0] == cyc[-1]
    assert set(cyc) == {"a", "b"}


def test_no_cycle_returns_none():
    g = mk(N("a"), N("b", needs=("a",)))
    assert algos.detect_cycle(g) is None


def test_topo_raises_on_cycle():
    g = mk(N("a", needs=("b",)), N("b", needs=("a",)))
    with pytest.raises(CycleError):
        algos.topo_sort(g)


def test_self_loop_is_a_cycle():
    g = mk(N("a", needs=("a",)))
    assert algos.detect_cycle(g) is not None


def test_critical_path():
    g = mk(N("a"), N("b", needs=("a",)), N("c", needs=("b",)), N("x", needs=("a",)))
    assert algos.critical_path(g) == ["a", "b", "c"]


def test_critical_path_empty():
    assert algos.critical_path(Graph()) == []
