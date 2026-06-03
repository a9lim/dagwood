"""Auto-install the dagwood MCP server into a client's config.

JSON clients (claude-code, claude-desktop, cursor, windsurf) share the
{"mcpServers": {"dagwood": {...}}} shape. Codex uses TOML ([mcp_servers.dagwood]),
round-tripped with tomlkit so existing comments/formatting survive. Other
clients are snippet-only (use `dag snippet <client>`).

A single <file>.dagwood.bak backup is written before each change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

from .snippet import SERVER_NAME, command_and_args


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return cast("dict[str, Any]", data) if isinstance(data, dict) else {}


def _backup_and_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.parent / (path.name + ".dagwood.bak")
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(text, encoding="utf-8")


def _install_json(path: Path, command: str, args: list[str], *, dry_run: bool, force: bool) -> int:
    data = _read_json(path)
    raw = data.get("mcpServers")
    servers: dict[str, Any] = cast("dict[str, Any]", raw) if isinstance(raw, dict) else {}
    desired: dict[str, Any] = {"command": command, "args": args}
    existing = servers.get(SERVER_NAME)
    if existing == desired:
        print(f"already installed: {path}")
        return 0
    if existing is not None and not force:
        print(f"refusing: '{SERVER_NAME}' already configured in {path} (use --force)", file=sys.stderr)
        return 1
    servers[SERVER_NAME] = desired
    data["mcpServers"] = servers
    text = json.dumps(data, indent=2) + "\n"
    if dry_run:
        print(f"# would write {path}:\n{text}")
        return 0
    _backup_and_write(path, text)
    print(f"installed dagwood -> {path}")
    return 0


def _install_toml(path: Path, command: str, args: list[str], *, dry_run: bool, force: bool) -> int:
    import tomlkit

    doc: Any = tomlkit.parse(path.read_text(encoding="utf-8")) if path.exists() else tomlkit.document()
    servers: Any = doc.get("mcp_servers")
    if servers is None:
        servers = tomlkit.table(is_super_table=True)
        doc["mcp_servers"] = servers
    existing: Any = servers.get(SERVER_NAME)
    if existing is not None and not force:
        same = existing.get("command") == command and list(existing.get("args", [])) == args
        if not same:
            print(f"refusing: '{SERVER_NAME}' already configured in {path} (use --force)", file=sys.stderr)
            return 1
    table: Any = tomlkit.table()
    table["command"] = command
    table["args"] = args
    servers[SERVER_NAME] = table
    text = tomlkit.dumps(doc)
    if dry_run:
        print(f"# would write {path}:\n{text}")
        return 0
    _backup_and_write(path, text)
    print(f"installed dagwood -> {path}")
    return 0


def install(client_name: str, *, dev_path: str | None = None, dry_run: bool = False, force: bool = False) -> int:
    from ._clients import CLIENTS

    rec = CLIENTS.get(client_name)
    if rec is None:
        print(f"unknown client: {client_name}\nknown: {', '.join(CLIENTS)}", file=sys.stderr)
        return 2
    if rec.path_fn is None or rec.fmt == "none":
        print(f"{client_name} is snippet-only — run `dag snippet {client_name}`", file=sys.stderr)
        return 2
    command, args = command_and_args(dev_path)
    path = rec.path_fn()
    if rec.fmt == "json":
        return _install_json(path, command, args, dry_run=dry_run, force=force)
    if rec.fmt == "toml":
        return _install_toml(path, command, args, dry_run=dry_run, force=force)
    print(f"no installer for format {rec.fmt!r}", file=sys.stderr)
    return 2


def uninstall(client_name: str) -> int:
    from ._clients import CLIENTS

    rec = CLIENTS.get(client_name)
    if rec is None or rec.path_fn is None:
        print(f"cannot uninstall {client_name}", file=sys.stderr)
        return 2
    path = rec.path_fn()
    if not path.exists():
        print(f"nothing to do: {path} does not exist")
        return 0

    if rec.fmt == "json":
        data = _read_json(path)
        raw = data.get("mcpServers")
        if isinstance(raw, dict):
            servers = cast("dict[str, Any]", raw)
            if SERVER_NAME in servers:
                del servers[SERVER_NAME]
                _backup_and_write(path, json.dumps(data, indent=2) + "\n")
                print(f"removed dagwood from {path}")
                return 0
    elif rec.fmt == "toml":
        import tomlkit

        doc: Any = tomlkit.parse(path.read_text(encoding="utf-8"))
        servers = doc.get("mcp_servers")
        if servers is not None and SERVER_NAME in servers:
            del servers[SERVER_NAME]
            _backup_and_write(path, tomlkit.dumps(doc))
            print(f"removed dagwood from {path}")
            return 0

    print(f"dagwood not found in {path}")
    return 0
