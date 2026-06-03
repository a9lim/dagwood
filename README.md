# dagwood

A DAG-native task tracker. Tasks are **nodes**; dependencies are **edges**. The
killer primitive is the **frontier** — the set of not-done tasks whose
dependencies are all complete, i.e. *what's actionable right now*.

- **One file is the source of truth.** A human-readable, git-diffable
  `.dag/dag.toml` per repo. The canvas, the agent (over MCP), and git are three
  windows onto it.
- **Live web canvas.** A Svelte Flow editor where you build and reshape the graph;
  as coding agents work the project over MCP, nodes turn green in real time.
- **Per-repo.** `.dag/` lives in your project like `.git`.

Status: early build. The pure engine (`dagwood.core`) lands first; the live server,
canvas, and MCP layer follow. See the milestone plan in the project notes.

## Model

- One edge type: `depends-on`. Status is `todo` / `doing` / `done`.
- `ready` / `blocked` / `frontier` are **derived**, never stored.
- Cycles are rejected at edge-creation; the graph is always a DAG.

## License

AGPL-3.0-or-later.
