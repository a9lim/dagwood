import json
from pathlib import Path

import pytest

from dagwood.core import toml_io
from dagwood.live.store import MutationError, Store


def make_store(tmp_path: Path) -> Store:
    dag = tmp_path / ".dag" / "dag.toml"
    dag.parent.mkdir(parents=True)
    dag.write_text("version = 1\n", encoding="utf-8")
    return Store(dag, tmp_path / ".dag" / "layout.json")


def test_apply_add_node_writes_file(tmp_path: Path):
    s = make_store(tmp_path)
    patch = s.apply_mutation({"type": "add_node", "title": "hello"}, now="t0")
    assert patch["type"] == "patch"
    assert len(patch["added"]) == 1
    nid = patch["added"][0]["id"]
    assert nid in s.graph.nodes
    assert nid in toml_io.load_toml(s.dag_path).nodes


def test_patch_carries_derived_and_op_id(tmp_path: Path):
    s = make_store(tmp_path)
    patch = s.apply_mutation({"type": "add_node", "title": "x"}, now="t0", op_id="op1")
    assert patch["op_id"] == "op1"
    assert "frontier" in patch["derived"]
    # a lone todo node with no deps is on the frontier
    assert patch["added"][0]["id"] in patch["derived"]["frontier"]


def test_self_write_suppressed(tmp_path: Path):
    s = make_store(tmp_path)
    s.apply_mutation({"type": "add_node", "title": "x"}, now="t0")
    assert s.reload_if_external() is None  # our own write — suppressed


def test_external_change_reloads(tmp_path: Path):
    s = make_store(tmp_path)
    s.dag_path.write_text(
        'version = 1\n\n[[node]]\nid = "z1"\ntitle = "ext"\nstatus = "todo"\nneeds = []\n',
        encoding="utf-8",
    )
    msg = s.reload_if_external()
    assert msg is not None and msg["type"] == "snapshot"
    assert "z1" in s.graph.nodes


def test_external_unparseable_yields_status(tmp_path: Path):
    s = make_store(tmp_path)
    s.dag_path.write_text("this is not = = = toml", encoding="utf-8")
    msg = s.reload_if_external()
    assert msg is not None and msg["type"] == "status" and msg["parse_ok"] is False


def test_cycle_mutation_rejected_no_write(tmp_path: Path):
    s = make_store(tmp_path)
    a = s.apply_mutation({"type": "add_node", "title": "a"}, now="t0")["added"][0]["id"]
    b = s.apply_mutation({"type": "add_node", "title": "b", "needs": [a]}, now="t0")["added"][0]["id"]
    before = s.dag_path.read_text(encoding="utf-8")
    with pytest.raises(MutationError) as ei:
        s.apply_mutation({"type": "add_edge", "src": b, "dst": a}, now="t0")
    assert ei.value.code == "cycle"
    assert s.dag_path.read_text(encoding="utf-8") == before  # unchanged


def test_unknown_node_is_not_found(tmp_path: Path):
    s = make_store(tmp_path)
    with pytest.raises(MutationError) as ei:
        s.apply_mutation({"type": "set_status", "id": "ghost", "status": "done"}, now="t0")
    assert ei.value.code == "not_found"


def test_bad_request_on_missing_field(tmp_path: Path):
    s = make_store(tmp_path)
    with pytest.raises(MutationError) as ei:
        s.apply_mutation({"type": "add_node"}, now="t0")  # no title
    assert ei.value.code == "bad_request"


def test_layout_persist(tmp_path: Path):
    s = make_store(tmp_path)
    s.handle_layout({"type": "set_layout", "id": "a", "x": 12, "y": 34})
    data = json.loads((tmp_path / ".dag" / "layout.json").read_text(encoding="utf-8"))
    assert data["overrides"]["a"] == {"x": 12.0, "y": 34.0}
