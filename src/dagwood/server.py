"""MCP server: lets coding agents (Claude Code, Codex, ...) drive the DAG.

Thin by design — every tool resolves the repo's .dag/dag.toml and delegates to
the pure engine. Reads load the file directly; writes take an advisory lock
(so concurrent agents don't race) and atomically rewrite the file. A running
`dag serve` notices the change via its watcher and updates the canvas live; if
no server is running, the next `dag serve` picks it up.

Tool descriptions are module-level FRAME constants (locked by test_server.py).
The handler functions (tool_*) are module-level and pure-ish so tests call them
directly with a temp .dag path.
"""

from __future__ import annotations

import fcntl
import os
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from . import oplog
from .core import algos, toml_io
from .core import graph as graph_ops
from .core.errors import CycleError, DagError, NodeNotFound, ValidationError
from .core.model import Graph

# ---------------------------------------------------------------------------
# Tool description frames. test_server.py locks these.
# ---------------------------------------------------------------------------

DAGWOOD_INSTRUCTIONS = (
    "dagwood tracks tasks as a dependency DAG. The 'frontier' is the set of "
    "not-done tasks whose dependencies are all complete — i.e. what is "
    "actionable right now. Typical loop: call dag_next to see what to work on, "
    "do one, call dag_done to mark it complete (it reports what that unblocked), "
    "repeat. Reads are always safe; dag_add / dag_link / dag_done / dag_set_status "
    "mutate the .dag/dag.toml in the current repo."
)

DAG_NEXT_FRAME = (
    "List the tasks actionable right now: not done, with every dependency "
    "complete (the DAG frontier). Read-only.\n"
    "Parameters:\n- limit: max tasks to return (default 20).\n"
    "Returns: {ready: [{id, title, status}], count}."
)

DAG_DONE_FRAME = (
    "Mark a task done, and report what it just unblocked so you can pick the "
    "next thing.\n"
    "Parameters:\n- id: task id.\n"
    'Returns: {id, status: "done", newly_ready: [{id, title, status}]}.'
)

DAG_SET_STATUS_FRAME = (
    "Set a task's status.\n"
    'Parameters:\n- id: task id.\n- status: "todo" | "doing" | "done".\n'
    "Returns: {id, status, newly_ready: [{id, title, status}]}."
)

DAG_SHOW_FRAME = (
    "Inspect the whole graph or a single task. Read-only.\n"
    "Parameters:\n- id: optional task id; omit for a graph summary.\n"
    "Returns (with id): {id, title, status, notes, needs, dependents, ready, "
    "blocked, unmet_needs: [{id, title, status}]}.\n"
    "Returns (no id): {count, by_status, frontier: [{id, title, status}], blocked_count}."
)

DAG_WHY_BLOCKED_FRAME = (
    "Explain why a task is not actionable yet. Read-only.\n"
    "Parameters:\n- id: task id.\n"
    "Returns: {blocked: bool, unmet_needs: [{id, title, status}]}."
)

DAG_ADD_FRAME = (
    "Create a task, optionally with prerequisites (existing task ids it depends on).\n"
    "Parameters:\n- title: task title.\n- needs: optional list of prerequisite "
    "task ids.\n- notes: optional notes.\n"
    "Returns: {id, title, ready}."
)

DAG_LINK_FRAME = (
    "Add a dependency edge: dst depends on src (src must finish before dst). "
    "Rejected if it would create a cycle.\n"
    "Parameters:\n- src: prerequisite task id.\n- dst: dependent task id.\n"
    "Returns: {ok: true, src, dst}."
)

DAG_UNLINK_FRAME = (
    "Remove the dependency edge src -> dst.\n"
    "Parameters:\n- src: prerequisite task id.\n- dst: dependent task id.\n"
    "Returns: {ok: true, src, dst}."
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_dag() -> Path:
    env = os.environ.get("DAGWOOD_DAG_PATH")
    if env:
        return Path(env)
    cwd = Path.cwd()
    for d in (cwd, *cwd.parents):
        candidate = d / ".dag" / "dag.toml"
        if candidate.exists():
            return candidate
    return cwd / ".dag" / "dag.toml"


def _load(dag_path: Path) -> Graph:
    if not dag_path.exists():
        return Graph()
    try:
        return toml_io.load_toml(dag_path)
    except DagError as e:
        raise ToolError(f"{dag_path} is invalid: {e}") from e


@contextmanager
def _locked(dag_path: Path) -> Generator[None, None, None]:
    dag_path.parent.mkdir(parents=True, exist_ok=True)
    lock = dag_path.parent / "dag.toml.lock"
    with open(lock, "w") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _save_and_log(
    dag_path: Path,
    g: Graph,
    now: str,
    op: str,
    *,
    added: list[str] | None = None,
    updated: list[str] | None = None,
    removed: list[str] | None = None,
) -> None:
    toml_io.save_toml(dag_path, g)
    oplog.append(
        dag_path.parent / "ops.jsonl",
        {
            "ts": now,
            "source": "mcp",
            "op": op,
            "op_id": None,
            "added": added or [],
            "updated": updated or [],
            "removed": removed or [],
        },
    )


def _brief(g: Graph, nid: str) -> dict[str, Any]:
    n = g.nodes[nid]
    return {"id": n.id, "title": n.title, "status": n.status}


# ---------------------------------------------------------------------------
# Tool handlers (module-level for direct testing).
# ---------------------------------------------------------------------------


def tool_next(dag_path: Path, limit: int = 20) -> dict[str, Any]:
    g = _load(dag_path)
    fr = algos.frontier(g)
    return {"ready": [_brief(g, i) for i in fr[: max(0, limit)]], "count": len(fr)}


def tool_show(dag_path: Path, nid: str | None = None) -> dict[str, Any]:
    g = _load(dag_path)
    if nid is None:
        by = {"todo": 0, "doing": 0, "done": 0}
        for n in g.nodes.values():
            by[n.status] += 1
        return {
            "count": len(g.nodes),
            "by_status": by,
            "frontier": [_brief(g, i) for i in algos.frontier(g)],
            "blocked_count": len(algos.blocked_nodes(g)),
        }
    if nid not in g.nodes:
        raise ToolError(f"no such task: {nid}")
    n = g.nodes[nid]
    dependents = [d for d in g.nodes if nid in g.nodes[d].needs]
    return {
        "id": n.id,
        "title": n.title,
        "status": n.status,
        "notes": n.notes,
        "needs": list(n.needs),
        "dependents": dependents,
        "ready": algos.is_ready(g, nid),
        "blocked": algos.is_blocked(g, nid),
        "unmet_needs": [_brief(g, d) for d in algos.why_blocked(g, nid)],
    }


def tool_why_blocked(dag_path: Path, nid: str) -> dict[str, Any]:
    g = _load(dag_path)
    if nid not in g.nodes:
        raise ToolError(f"no such task: {nid}")
    return {"blocked": algos.is_blocked(g, nid), "unmet_needs": [_brief(g, d) for d in algos.why_blocked(g, nid)]}


def tool_add(
    dag_path: Path,
    title: str,
    needs: list[str] | None = None,
    notes: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    now = now or _now()
    with _locked(dag_path):
        g = _load(dag_path)
        try:
            g, nid = graph_ops.add_node(g, title, notes=notes, needs=needs or [], now=now)
        except (NodeNotFound, ValidationError) as e:
            raise ToolError(str(e)) from e
        _save_and_log(dag_path, g, now, "add_node", added=[nid])
    return {"id": nid, "title": title, "ready": algos.is_ready(g, nid)}


def _set_status(dag_path: Path, nid: str, status: str, now: str | None) -> dict[str, Any]:
    now = now or _now()
    with _locked(dag_path):
        g = _load(dag_path)
        if nid not in g.nodes:
            raise ToolError(f"no such task: {nid}")
        before = set(algos.frontier(g))
        try:
            g = graph_ops.set_status(g, nid, status, now=now)
        except ValidationError as e:
            raise ToolError(str(e)) from e
        _save_and_log(dag_path, g, now, "set_status", updated=[nid])
        newly = [_brief(g, i) for i in algos.frontier(g) if i not in before]
    return {"id": nid, "status": status, "newly_ready": newly}


def tool_done(dag_path: Path, nid: str, now: str | None = None) -> dict[str, Any]:
    return _set_status(dag_path, nid, "done", now)


def tool_set_status(dag_path: Path, nid: str, status: str, now: str | None = None) -> dict[str, Any]:
    return _set_status(dag_path, nid, status, now)


def tool_link(dag_path: Path, src: str, dst: str, now: str | None = None) -> dict[str, Any]:
    now = now or _now()
    with _locked(dag_path):
        g = _load(dag_path)
        try:
            g = graph_ops.add_edge(g, src, dst, now=now)
        except (CycleError, NodeNotFound, ValidationError) as e:
            raise ToolError(str(e)) from e
        _save_and_log(dag_path, g, now, "add_edge", updated=[dst])
    return {"ok": True, "src": src, "dst": dst}


def tool_unlink(dag_path: Path, src: str, dst: str, now: str | None = None) -> dict[str, Any]:
    now = now or _now()
    with _locked(dag_path):
        g = _load(dag_path)
        try:
            g = graph_ops.remove_edge(g, src, dst, now=now)
        except NodeNotFound as e:
            raise ToolError(str(e)) from e
        _save_and_log(dag_path, g, now, "remove_edge", updated=[dst])
    return {"ok": True, "src": src, "dst": dst}


# ---------------------------------------------------------------------------
# Server assembly.
# ---------------------------------------------------------------------------


def build_server(dag_path: str | os.PathLike[str] | None = None) -> FastMCP:
    path = Path(dag_path) if dag_path is not None else _resolve_dag()
    mcp = FastMCP(name="dagwood", instructions=DAGWOOD_INSTRUCTIONS)

    @mcp.tool(name="dag_next", description=DAG_NEXT_FRAME)
    def dag_next(limit: int = 20) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return tool_next(path, limit)

    @mcp.tool(name="dag_show", description=DAG_SHOW_FRAME)
    def dag_show(id: str | None = None) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return tool_show(path, id)

    @mcp.tool(name="dag_why_blocked", description=DAG_WHY_BLOCKED_FRAME)
    def dag_why_blocked(id: str) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return tool_why_blocked(path, id)

    @mcp.tool(name="dag_add", description=DAG_ADD_FRAME)
    def dag_add(title: str, needs: list[str] | None = None, notes: str = "") -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return tool_add(path, title, needs, notes)

    @mcp.tool(name="dag_done", description=DAG_DONE_FRAME)
    def dag_done(id: str) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return tool_done(path, id)

    @mcp.tool(name="dag_set_status", description=DAG_SET_STATUS_FRAME)
    def dag_set_status(id: str, status: str) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return tool_set_status(path, id, status)

    @mcp.tool(name="dag_link", description=DAG_LINK_FRAME)
    def dag_link(src: str, dst: str) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return tool_link(path, src, dst)

    @mcp.tool(name="dag_unlink", description=DAG_UNLINK_FRAME)
    def dag_unlink(src: str, dst: str) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return tool_unlink(path, src, dst)

    return mcp


def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    build_server().run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
