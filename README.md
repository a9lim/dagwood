# dagwood

[![CI](https://github.com/a9lim/dagwood/actions/workflows/ci.yml/badge.svg)](https://github.com/a9lim/dagwood/actions/workflows/ci.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

dagwood is a task tracker built on a DAG. Tasks are nodes, dependencies are edges, and the thing it cares about most is the frontier: the tasks that aren't done yet and have all their dependencies done. That set is everything you can actually work on right now.

I built this because list trackers and gantt charts never fit how I think about work. A flat list is too little; it can't say that B has to happen after A. A gantt chart is too much; I don't want to put dates and durations on everything just to express an ordering. What I actually keep in my head is a big graph of tasks pointing at each other, so dagwood just lets me write that graph down and then tells me what's unblocked.

The whole state of a project is one file, `.dag/dag.toml`, and it lives in the repo next to your code. The web canvas, an agent over MCP, and git are all windows onto that one file.

## Install

dagwood isn't on PyPI yet, so for now it's a source checkout. You need Python
3.11+ and Node (for building the canvas).

```sh
git clone https://github.com/a9lim/dagwood
cd dagwood
python -m pip install -e ".[dev]"      # install into system Python 3.12
cd web && npm install && npm run build  # build the canvas into the package
cd ..
```

The canvas build step matters: the built bundle is what `dag serve` serves, and it isn't checked in. If you skip it you get a placeholder page instead of the canvas.

## Quickstart

```sh
cd ~/your-project
dag init       # writes .dag/dag.toml and a .gitignore for the local sidecar files
dag serve      # live server + canvas on http://127.0.0.1:8765
```

Open that URL and you get the canvas. Double-click empty space to add a task, drag from one task's bottom handle to another's top handle to add a dependency, and click a task to edit its title, status, or notes. Everything you do writes straight to `.dag/dag.toml`, which you commit alongside your code. Tasks are tinted by state: green for done, blue for ready (on the frontier), dimmed for blocked.

## Use it with a coding agent

dagwood speaks MCP, so Claude Code, Codex, and similar tools can read the graph and update it while they work.

```sh
dag install claude-code   # writes the server into ~/.claude.json
dag install codex         # ~/.codex/config.toml
```

The agent gets these tools:

| Tool | What it does |
|------|--------------|
| `dag_next` | The tasks you can work on right now (the frontier) |
| `dag_done` | Mark a task done; returns what that just unblocked |
| `dag_add` | Create a task, optionally with prerequisites |
| `dag_link` / `dag_unlink` | Add or remove a dependency edge |
| `dag_show` | Inspect the whole graph or a single task |
| `dag_why_blocked` | Explain why a task isn't actionable yet |
| `dag_set_status` | Set a task to todo, doing, or done |

The loop dagwood is built around: the agent calls `dag_next` to see what it can pick up, does one, calls `dag_done` to mark it complete (which tells it what that unblocked), and goes again. If you have `dag serve` open while the agent works, the canvas updates live as nodes go green.

For clients without auto-install, `dag snippet <client>` prints the config to paste in (it covers opencode, vscode, and zed on top of the ones above).

## The file

`.dag/dag.toml` is the entire state of a project:

```toml
version = 1

[[node]]
id = "a3f"
title = "Design the schema"
status = "done"
needs = []

[[node]]
id = "b71"
title = "Build the engine"
status = "doing"
needs = ["a3f"]      # b71 depends on a3f; a3f has to finish first
```

Status is `todo`, `doing`, or `done`. `ready` and `blocked` are never stored; they're computed from the edges. A task is ready when it isn't done and all of its `needs` are done, and that set is exactly the frontier. Cycles are rejected when you make the edge, so the graph is always acyclic.

Canvas positions don't go in `dag.toml`. They live in `.dag/layout.json`, which `dag init` gitignores, so dragging a node around never shows up in your diff. The mutation log is `.dag/ops.jsonl` (also gitignored), which `dag log` reads.

## CLI

```
dag init [dir]            scaffold .dag/ in a repo (default: cwd)
dag serve                 run the live server + canvas (127.0.0.1:8765)
dag mcp                   run the MCP server over stdio (what `dag install` wires up)
dag doctor                read-only health check (counts, frontier, cycles, orphans)
dag log [-n N]            recent mutations from .dag/ops.jsonl
dag install <client>      register the MCP server (claude-code, codex, claude-desktop, cursor, windsurf)
dag uninstall <client>    remove it
dag snippet <client>      print paste-able config (also opencode, vscode, zed)
```

`python -m dagwood <command>` does the same thing.

## A note on scope

dagwood is a single-user local tool. `dag serve` binds to `127.0.0.1` and has no auth or sandboxing. Please don't put it on a public interface. When an agent over MCP and you on the canvas both edit at the same instant it's last-write-wins on that one write; in practice you and the agent aren't usually touching the same task in the same millisecond, and the next change reconciles.

## Architecture

```
src/dagwood/
  core/        pure engine: Node/Graph, ids, frontier + cycle detection, TOML round-trip
  live/        Starlette server: sole-writer store, file watcher, websocket, layout sidecar
  server.py    MCP server (FastMCP over stdio)
  installer.py, snippet.py, _clients.py    `dag install` / `dag snippet` for MCP clients
  cli.py       the `dag` command
  oplog.py     append-only mutation log
web/           Svelte 5 + Vite canvas, built into src/dagwood/live/static
```

## License

AGPL-3.0-or-later.
