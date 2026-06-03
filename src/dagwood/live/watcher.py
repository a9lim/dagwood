"""Filesystem watcher: catches external edits to dag.toml (git, hand-edit, an
agent writing while the server is down) and rebroadcasts.

We watch the PARENT directory rather than the file itself because the store's
atomic write (os.replace) swaps the inode, which file-level watchers miss.
The store's own writes are suppressed inside `reload_if_external` by comparing
the on-disk text to the last text we wrote.
"""

from __future__ import annotations

from .store import Store


async def run(store: Store) -> None:
    from watchfiles import awatch  # type: ignore[reportUnknownVariableType]

    async for _changes in awatch(str(store.dag_path.parent), debounce=200):  # type: ignore[reportUnknownVariableType]
        msg = store.reload_if_external()
        if msg is not None:
            store.broadcast(msg)
