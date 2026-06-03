import pytest

from dagwood.core import toml_io
from dagwood.core.errors import CycleError, ValidationError
from dagwood.core.model import Graph, Node

TEXT = """version = 1

[meta]
title = "demo"

[[node]]
id = "a3f"
title = "Design schema"
status = "done"
needs = []
created = "2026-06-02T10:00:00Z"
updated = "2026-06-02T11:30:00Z"

[[node]]
id = "b71"
title = "Build engine"
status = "doing"
needs = ["a3f"]
"""


def test_load_basic():
    g = toml_io.loads(TEXT)
    assert set(g.nodes) == {"a3f", "b71"}
    assert g.meta["title"] == "demo"
    assert g.nodes["a3f"].status == "done"
    assert g.nodes["b71"].needs == ("a3f",)
    assert g.nodes["a3f"].created == "2026-06-02T10:00:00Z"


def test_round_trip_fixed_point():
    g1 = toml_io.loads(TEXT)
    t1 = toml_io.dump_toml(g1)
    g2 = toml_io.loads(t1)
    t2 = toml_io.dump_toml(g2)
    assert t1 == t2
    assert g1 == g2


def test_dump_is_deterministic():
    g = toml_io.loads(TEXT)
    assert toml_io.dump_toml(g) == toml_io.dump_toml(g)


def test_reject_cycle_on_load():
    bad = """version = 1
[[node]]
id = "a"
title = "A"
needs = ["b"]
[[node]]
id = "b"
title = "B"
needs = ["a"]
"""
    with pytest.raises(CycleError):
        toml_io.loads(bad)


def test_reject_unknown_needs():
    bad = """version = 1
[[node]]
id = "a"
title = "A"
needs = ["ghost"]
"""
    with pytest.raises(ValidationError):
        toml_io.loads(bad)


def test_reject_bad_version():
    with pytest.raises(ValidationError):
        toml_io.loads("version = 2\n")


def test_notes_special_chars_round_trip():
    notes = 'line1\nline2 with "quotes" and \\ backslash\ttab'
    g = Graph(nodes={"a": Node(id="a", title="A", notes=notes)})
    reloaded = toml_io.loads(toml_io.dump_toml(g))
    assert reloaded.nodes["a"].notes == notes


def test_file_round_trip(tmp_path):
    g = toml_io.loads(TEXT)
    p = tmp_path / ".dag" / "dag.toml"
    toml_io.save_toml(p, g)
    g2 = toml_io.load_toml(p)
    assert g == g2
    assert p.read_text(encoding="utf-8").endswith("\n")
