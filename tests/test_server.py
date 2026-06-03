from pathlib import Path

from starlette.testclient import TestClient

from dagwood.core import toml_io
from dagwood.live.app import create_app


def make_app(tmp_path: Path):
    dag = tmp_path / ".dag" / "dag.toml"
    dag.parent.mkdir(parents=True)
    dag.write_text("version = 1\n", encoding="utf-8")
    return create_app(dag, watch=False), dag


def test_healthz_and_graph(tmp_path: Path):
    app, _ = make_app(tmp_path)
    with TestClient(app) as c:
        assert c.get("/healthz").json()["parse_ok"] is True
        assert c.get("/api/graph").json()["type"] == "snapshot"


def test_ws_snapshot_then_patch(tmp_path: Path):
    app, dag = make_app(tmp_path)
    with TestClient(app) as c, c.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "snapshot"
        ws.send_json({"type": "add_node", "title": "hi", "op_id": "o1"})
        patch = ws.receive_json()
        assert patch["type"] == "patch"
        assert patch["op_id"] == "o1"
        assert len(patch["added"]) == 1
    assert len(toml_io.load_toml(dag).nodes) == 1


def test_ws_cycle_error_no_write(tmp_path: Path):
    app, dag = make_app(tmp_path)
    with TestClient(app) as c, c.websocket_connect("/ws") as ws:
        ws.receive_json()  # snapshot
        ws.send_json({"type": "add_node", "title": "a", "op_id": "1"})
        a = ws.receive_json()["added"][0]["id"]
        ws.send_json({"type": "add_node", "title": "b", "needs": [a], "op_id": "2"})
        b = ws.receive_json()["added"][0]["id"]
        before = dag.read_text(encoding="utf-8")
        ws.send_json({"type": "add_edge", "src": b, "dst": a, "op_id": "3"})
        err = ws.receive_json()
        assert err["type"] == "error" and err["code"] == "cycle" and err["op_id"] == "3"
        assert dag.read_text(encoding="utf-8") == before


def test_post_mutate(tmp_path: Path):
    app, dag = make_app(tmp_path)
    with TestClient(app) as c:
        r = c.post("/api/mutate", json={"type": "add_node", "title": "viaPOST"})
        assert r.status_code == 200 and r.json()["type"] == "patch"
    assert any(n.title == "viaPOST" for n in toml_io.load_toml(dag).nodes.values())


def test_post_mutate_cycle_400(tmp_path: Path):
    app, _ = make_app(tmp_path)
    with TestClient(app) as c:
        a = c.post("/api/mutate", json={"type": "add_node", "title": "a"}).json()["added"][0]["id"]
        b = c.post("/api/mutate", json={"type": "add_node", "title": "b", "needs": [a]}).json()["added"][0]["id"]
        r = c.post("/api/mutate", json={"type": "add_edge", "src": b, "dst": a})
        assert r.status_code == 400 and r.json()["code"] == "cycle"


def test_layout_get_put(tmp_path: Path):
    app, _ = make_app(tmp_path)
    with TestClient(app) as c:
        put = c.put("/api/layout", json={"overrides": {"n1": {"x": 5, "y": 6}}, "viewport": {"x": 0, "y": 0, "zoom": 1}})
        assert put.status_code == 200
        got = c.get("/api/layout").json()
        assert got["overrides"]["n1"] == {"x": 5.0, "y": 6.0}
