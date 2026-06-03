# AGENTS.md — dagwood

Working notes for agents editing this repo. Global rules still apply.

## What this is

A DAG-native task tracker. Tasks are nodes; dependencies are `depends-on` edges. The **frontier** is the set of not-done nodes whose every dependency is done (i.e. what's actionable now). The whole state of a project is one `.dag/dag.toml`; a live Starlette server, a Svelte canvas, and an MCP server are all views onto it.

The killer primitive is the frontier, and the design rule that makes everything else fall out is: **the on-disk file is the single source of truth, and the running server is its only writer.**

## Architecture

```
src/dagwood/
  core/              # PURE engine. Zero imports from live/, server, mcp, starlette.
    model.py         # Node (frozen) + Graph dataclasses; Status = todo|doing|done
    ids.py           # short stable Crockford-base32 ids (lowercase, no i/l/o/u)
    errors.py        # DagError hierarchy: ValidationError, NodeNotFound, DuplicateId, CycleError
    algos.py         # hand-rolled (no networkx): Kahn topo_sort, detect_cycle (iterative
                     # 3-colour DFS), frontier, blocked_nodes, why_blocked, critical_path
    graph.py         # copy-on-write mutations: add/remove node+edge, set_status, set_fields.
                     # acyclicity enforced HERE (and in toml_io.load_toml), nowhere else.
    toml_io.py       # deterministic TOML round-trip + atomic_write_text. Read via stdlib
                     # tomllib; write via a hand-rolled serializer (stable field order,
                     # canonical escaping) so diffs stay clean.
  live/              # Starlette ASGI layer. The file's only writer when running.
    store.py         # authoritative in-memory Graph + SOLE WRITER of dag.toml. Mutation
                     # logic is synchronous, so in asyncio's single thread each mutation is
                     # atomic w.r.t. concurrent ws handlers (no lock). Also writes ops.jsonl.
    watcher.py       # watchfiles on the .dag/ dir; on an external edit, reload + broadcast.
                     # self-writes are suppressed by comparing on-disk text to last-written.
    protocol.py      # ws message builders: snapshot / patch / error / status. derived
                     # (frontier, blocked) rides on every snapshot/patch.
    layout.py        # geometry sidecar (.dag/layout.json) load/save. NEVER touches dag.toml.
    app.py           # create_app(): routes (/api/graph, /api/layout, /api/mutate, /healthz),
                     # /ws, static mount, lifespan that runs the watcher. Binds 127.0.0.1.
  server.py          # MCP (FastMCP over stdio). Tools share core. Writes take an flock and
                     # atomically rewrite dag.toml; a running server adopts the change via its
                     # watcher. Tool descriptions are *_FRAME constants, locked by tests.
  installer.py       # `dag install` / `dag uninstall`: JSON clients (claude-code, claude-
                     # desktop, cursor, windsurf) + codex (TOML via tomlkit). One .dagwood.bak.
  snippet.py         # `dag snippet`: per-client config builders (adds opencode/vscode/zed).
  _clients.py        # the client registry (name, hint, fmt, path_fn, snippet builder).
  cli.py             # the `dag` console script: serve/init/doctor/log/mcp/install/uninstall/snippet
  oplog.py           # append-only JSONL mutation log (.dag/ops.jsonl), shared by live + mcp.
web/                 # Svelte 5 + Vite. Built into src/dagwood/live/static (gitignored).
  src/App.svelte     # SvelteFlowProvider wrapper
  src/Flow.svelte    # the canvas: SvelteFlow + ELK layout + editing handlers + HUD
  src/components/    # TaskNode.svelte (tinted by state), Inspector.svelte
  src/lib/           # ws.svelte.ts (reactive client), layout.ts (ELK), protocol.ts (mirror of live/protocol.py)
```

## Hard rules

1. **`core/` imports nothing from `live/`, `server.py`, `mcp`, or `starlette`.** It is the pure engine and must stay unit-testable with no runtime. This is what lets one engine back the server, the MCP tools, the CLI, and the tests.

2. **Acyclicity is enforced in exactly two places:** `core/graph.py` (on edge-creating mutations) and `core/toml_io.load_toml` (on load). Don't add cycle checks in the server, the canvas, or the MCP layer, and don't remove these two. Everyone else catches `CycleError` and translates it.

3. **`ready` / `blocked` / `frontier` are derived, never stored.** Only `status` (todo/doing/done) and the `needs` edges live in the file. Storing derived state creates a consistency hazard the moment any edit lands out of band.

4. **`dag.toml` stays purely semantic.** Canvas geometry goes in the `.dag/layout.json` sidecar, keyed by node id. Never write positions, colours, or zoom into `dag.toml`. A drag must not produce a `dag.toml` diff.

5. **The running server is the sole writer of `dag.toml`.** Canvas (ws), CLI, and (when the server is up) MCP all mutate through it. MCP-when-the-server-is-down writes the file directly under an `flock`, and the watcher reconciles. Keep this model; don't add a second concurrent writer.

6. **MCP tool description frames are contract.** They're the `DAG_*_FRAME` constants in `server.py` and `test_server.py` checks they exist. Changing a frame changes what the agent sees; update the test and get the user to sign off.

7. **Don't add MCP tools without approval.** The surface (`dag_next`, `dag_done`, `dag_set_status`, `dag_show`, `dag_why_blocked`, `dag_add`, `dag_link`, `dag_unlink`) is deliberately small. There is intentionally **no** node-deletion tool over MCP; deletion is a human action on the canvas. CLI subcommands are fine; they're out-of-band.

8. **`dump_toml` must stay deterministic.** Stable field order, canonical escaping, no comment dependence. There's a `load -> dump -> load -> dump` fixed-point test in `test_toml_io.py`; keep it green or git diffs turn noisy.

9. **The engine is time-pure.** Mutations take an optional `now=` and the live/MCP layers pass real time at the boundary. Don't call `datetime.now()` inside `core/`.

## Wire protocol

`live/protocol.py` and `web/src/lib/protocol.ts` are two halves of one contract. If you add a message type or a field, change both. Server to client: `snapshot`, `patch` (`{added, updated, removed, derived}`), `error` (`{code, message, op_id?}`), `status`. Client to server: `add_node`, `set_status`, `set_fields`, `add_edge`, `remove_edge`, `remove_node`, plus the geometry-only `set_layout` / `set_viewport`. Patches broadcast to everyone; errors go to the originator only.

## Style

- Python 3.11+. `pyright` strict on `src/dagwood`. `ruff` (E, F, W, I, UP, B), line length 120. `pytest`. hatchling. AGPL-3.0-or-later.
- Frontend: Svelte 5 runes, `svelte-check` clean. `@xyflow/svelte` is pinned to an exact version (it's alpha); isolate its API behind the components so a breaking bump is contained.
- Error messages are user-facing. Point at the fix.

## Testing

```sh
uv run pytest                 # full suite
uv run pyright                # strict on src/dagwood
uv run ruff check .
cd web && npm run check && npm run build   # svelte-check + build the canvas
```

The MCP server is exercised two ways: the `tool_*` handlers are called directly in `test_server.py`, and a live stdio round-trip (mcp client -> `dag mcp`) can be run against a temp `.dag` to confirm the transport. Reads load the file directly; only writes take the lock.

## Things that look like bugs but are not

- **Editor pyright reports newly-added modules as unresolvable** and flags print/argparse args as unknown-typed. Stale editor cache from before the venv saw the module; `uv run pyright` resolves it. Restart the pyright server to clear the noise.
- **`dag mcp` logs request lines to stderr.** That's the MCP SDK's own logging; stdout carries the JSON-RPC, so it's harmless. Never `print()` to stdout in the MCP path.
- **Re-running ELK on a status-only change doesn't move nodes.** ELK layered is deterministic for a fixed node/edge set, so the canvas re-derives positions without anything jumping. The async-token in `Flow.svelte` drops stale layout results.
- **MCP writes + a live server can lose an update** if a human canvas edit and an agent write land in the same millisecond (last-write-wins on that single atomic write; the watcher then adopts whatever hit disk). Documented in `server.py`. Fine for single-user; the airtight fix is to route MCP through the running server.
- **The built canvas isn't in the repo.** `web/` builds into `src/dagwood/live/static`, which is gitignored. A fresh clone serves a placeholder until you run the web build. Until a release packages the bundle, that build step is required.
