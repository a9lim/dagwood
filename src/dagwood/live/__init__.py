"""The live-sync layer: a Starlette server that makes the on-disk DAG live.

The on-disk `.dag/dag.toml` is the single source of truth. The running server
holds the authoritative in-memory Graph and is the ONLY writer of that file;
the canvas (websocket), the MCP layer, and the CLI all mutate through it. A file
watcher catches external edits (git, hand-edit) and rebroadcasts.
"""
