import pytest

from dagwood.core import Graph, graph
from dagwood.core.errors import CycleError, NodeNotFound, ValidationError


def test_add_node_returns_id_and_node():
    g0 = Graph()
    g1, nid = graph.add_node(g0, "task one")
    assert nid in g1.nodes
    assert g1.nodes[nid].title == "task one"
    assert g1.nodes[nid].status == "todo"
    assert g0.nodes == {}  # original untouched (copy-on-write)


def test_add_node_with_needs_and_validation():
    g0 = Graph()
    g1, a = graph.add_node(g0, "a")
    g2, b = graph.add_node(g1, "b", needs=[a])
    assert a in g2.nodes[b].needs
    with pytest.raises(NodeNotFound):
        graph.add_node(g2, "c", needs=["nope"])


def test_add_edge_and_cycle_rejection():
    g0 = Graph()
    g1, a = graph.add_node(g0, "a")
    g2, b = graph.add_node(g1, "b")
    g3 = graph.add_edge(g2, a, b)  # a is prerequisite of b
    assert a in g3.nodes[b].needs
    with pytest.raises(CycleError):
        graph.add_edge(g3, b, a)  # would close a cycle


def test_add_edge_idempotent():
    g0 = Graph()
    g1, a = graph.add_node(g0, "a")
    g2, b = graph.add_node(g1, "b")
    g3 = graph.add_edge(g2, a, b)
    g4 = graph.add_edge(g3, a, b)
    assert g4.nodes[b].needs.count(a) == 1


def test_self_edge_rejected():
    g0 = Graph()
    g1, a = graph.add_node(g0, "a")
    with pytest.raises(ValidationError):
        graph.add_edge(g1, a, a)


def test_remove_node_strips_dangling_needs():
    g0 = Graph()
    g1, a = graph.add_node(g0, "a")
    g2, b = graph.add_node(g1, "b", needs=[a])
    g3 = graph.remove_node(g2, a)
    assert a not in g3.nodes
    assert a not in g3.nodes[b].needs


def test_remove_edge():
    g0 = Graph()
    g1, a = graph.add_node(g0, "a")
    g2, b = graph.add_node(g1, "b", needs=[a])
    g3 = graph.remove_edge(g2, a, b)
    assert a not in g3.nodes[b].needs


def test_set_status():
    g0 = Graph()
    g1, a = graph.add_node(g0, "a")
    g2 = graph.set_status(g1, a, "done")
    assert g2.nodes[a].status == "done"
    with pytest.raises(ValidationError):
        graph.set_status(g2, a, "bogus")


def test_set_fields_updates_timestamp():
    g0 = Graph()
    g1, a = graph.add_node(g0, "a", now="t0")
    g2 = graph.set_fields(g1, a, title="renamed", now="t1")
    assert g2.nodes[a].title == "renamed"
    assert g2.nodes[a].updated == "t1"


def test_missing_node_errors():
    g0 = Graph()
    with pytest.raises(NodeNotFound):
        graph.set_status(g0, "ghost", "done")
    with pytest.raises(NodeNotFound):
        graph.remove_node(g0, "ghost")
