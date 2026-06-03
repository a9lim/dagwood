from pathlib import Path

import pytest

from dagwood import cli
from dagwood.core import graph as G
from dagwood.core import toml_io
from dagwood.core.model import Graph


def test_init_creates_files(tmp_path: Path):
    assert cli.main(["init", str(tmp_path)]) == 0
    assert (tmp_path / ".dag" / "dag.toml").exists()
    gi = (tmp_path / ".dag" / ".gitignore").read_text(encoding="utf-8")
    assert "layout.json" in gi
    assert "ops.jsonl" in gi


def test_init_idempotent(tmp_path: Path):
    assert cli.main(["init", str(tmp_path)]) == 0
    g, _ = G.add_node(toml_io.load_toml(tmp_path / ".dag" / "dag.toml"), "keep me")
    toml_io.save_toml(tmp_path / ".dag" / "dag.toml", g)
    assert cli.main(["init", str(tmp_path)]) == 0  # does not clobber
    assert len(toml_io.load_toml(tmp_path / ".dag" / "dag.toml").nodes) == 1


def test_doctor_ok(tmp_path: Path):
    g = Graph()
    g, a = G.add_node(g, "a")
    g, _ = G.add_node(g, "b", needs=[a])
    p = tmp_path / ".dag" / "dag.toml"
    toml_io.save_toml(p, g)
    assert cli.main(["doctor", "--path", str(p)]) == 0


def test_doctor_cycle_fails(tmp_path: Path):
    p = tmp_path / ".dag" / "dag.toml"
    p.parent.mkdir(parents=True)
    p.write_text(
        'version = 1\n[[node]]\nid="a"\ntitle="a"\nneeds=["b"]\n[[node]]\nid="b"\ntitle="b"\nneeds=["a"]\n',
        encoding="utf-8",
    )
    assert cli.main(["doctor", "--path", str(p)]) == 1


def test_doctor_missing_fails(tmp_path: Path):
    assert cli.main(["doctor", "--path", str(tmp_path / "nope.toml")]) == 1


def test_log_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    p = tmp_path / ".dag" / "dag.toml"
    toml_io.save_toml(p, Graph())
    assert cli.main(["log", "--path", str(p)]) == 0
    assert "no recorded operations" in capsys.readouterr().out
