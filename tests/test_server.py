import asyncio
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from dagwood import oplog, server
from dagwood.core import toml_io
from dagwood.core.model import Graph


def dagfile(tmp_path: Path) -> Path:
    p = tmp_path / ".dag" / "dag.toml"
    toml_io.save_toml(p, Graph())
    return p


def test_next_done_unblock_loop(tmp_path: Path):
    p = dagfile(tmp_path)
    a = server.tool_add(p, "a")["id"]
    b = server.tool_add(p, "b", needs=[a])["id"]
    # only a is actionable
    assert [r["id"] for r in server.tool_next(p)["ready"]] == [a]
    # completing a unblocks b, reported in newly_ready
    res = server.tool_done(p, a)
    assert res["status"] == "done"
    assert [n["id"] for n in res["newly_ready"]] == [b]
    assert [r["id"] for r in server.tool_next(p)["ready"]] == [b]


def test_add_with_needs_and_ready_flag(tmp_path: Path):
    p = dagfile(tmp_path)
    a = server.tool_add(p, "a")["id"]
    res = server.tool_add(p, "b", needs=[a])
    assert res["ready"] is False  # blocked by a
    assert server.tool_add(p, "c")["ready"] is True


def test_link_cycle_rejected(tmp_path: Path):
    p = dagfile(tmp_path)
    a = server.tool_add(p, "a")["id"]
    b = server.tool_add(p, "b", needs=[a])["id"]
    with pytest.raises(ToolError):
        server.tool_link(p, b, a)  # would close a cycle


def test_link_unlink(tmp_path: Path):
    p = dagfile(tmp_path)
    a = server.tool_add(p, "a")["id"]
    b = server.tool_add(p, "b")["id"]
    server.tool_link(p, a, b)
    assert server.tool_show(p, b)["needs"] == [a]
    server.tool_unlink(p, a, b)
    assert server.tool_show(p, b)["needs"] == []


def test_show_summary_and_detail(tmp_path: Path):
    p = dagfile(tmp_path)
    a = server.tool_add(p, "a")["id"]
    b = server.tool_add(p, "b", needs=[a])["id"]
    summary = server.tool_show(p)
    assert summary["count"] == 2
    assert [n["id"] for n in summary["frontier"]] == [a]
    detail = server.tool_show(p, b)
    assert detail["blocked"] and detail["unmet_needs"][0]["id"] == a
    assert detail["dependents"] == []


def test_why_blocked(tmp_path: Path):
    p = dagfile(tmp_path)
    a = server.tool_add(p, "a")["id"]
    b = server.tool_add(p, "b", needs=[a])["id"]
    wb = server.tool_why_blocked(p, b)
    assert wb["blocked"] and wb["unmet_needs"][0]["id"] == a


def test_unknown_task_errors(tmp_path: Path):
    p = dagfile(tmp_path)
    with pytest.raises(ToolError):
        server.tool_done(p, "ghost")
    with pytest.raises(ToolError):
        server.tool_show(p, "ghost")


def test_mcp_mutations_logged(tmp_path: Path):
    p = dagfile(tmp_path)
    server.tool_add(p, "a")
    recs = oplog.tail(p.parent / "ops.jsonl")
    assert recs and recs[-1]["source"] == "mcp" and recs[-1]["op"] == "add_node"


def test_build_server_registers_tools(tmp_path: Path):
    srv = server.build_server(dagfile(tmp_path))
    names = {t.name for t in asyncio.run(srv.list_tools())}
    assert {
        "dag_next",
        "dag_done",
        "dag_set_status",
        "dag_show",
        "dag_why_blocked",
        "dag_add",
        "dag_link",
        "dag_unlink",
    } <= names


def test_frames_are_nonempty_strings():
    for frame in (
        server.DAG_NEXT_FRAME,
        server.DAG_DONE_FRAME,
        server.DAG_SHOW_FRAME,
        server.DAG_WHY_BLOCKED_FRAME,
        server.DAG_ADD_FRAME,
        server.DAG_LINK_FRAME,
        server.DAG_UNLINK_FRAME,
        server.DAG_SET_STATUS_FRAME,
    ):
        assert isinstance(frame, str) and frame.strip()
