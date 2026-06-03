from pathlib import Path

from dagwood import oplog


def test_append_and_tail(tmp_path: Path):
    p = tmp_path / "ops.jsonl"
    for i in range(5):
        oplog.append(p, {"ts": f"t{i}", "op": "add_node", "added": [f"n{i}"]})
    recs = oplog.tail(p, 3)
    assert len(recs) == 3
    assert recs[-1]["added"] == ["n4"]
    assert recs[0]["ts"] == "t2"


def test_tail_missing(tmp_path: Path):
    assert oplog.tail(tmp_path / "none.jsonl") == []


def test_tail_skips_blank_and_bad_lines(tmp_path: Path):
    p = tmp_path / "ops.jsonl"
    p.write_text('{"op":"a"}\n\nnot json\n{"op":"b"}\n', encoding="utf-8")
    recs = oplog.tail(p)
    assert [r["op"] for r in recs] == ["a", "b"]
