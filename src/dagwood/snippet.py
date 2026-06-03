"""Emit paste-able MCP client config for dagwood.

Default assumes `dag` is on PATH (e.g. after `uv tool install dagwood`) and
emits command "dag", args ["mcp"]. `--dev-path /path/to/dagwood` emits a
`uv run --directory` variant for running from a source checkout.

Per-client snippet shapes live here; the client registry (which builder maps
to which client + config path) lives in _clients.py. run() defers its registry
import to break the cycle.
"""

from __future__ import annotations

import json
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

SERVER_NAME = "dagwood"

Builder = Callable[[str, list[str]], str]


def command_and_args(dev_path: str | None) -> tuple[str, list[str]]:
    if dev_path is not None:
        abs_path = str(Path(dev_path).expanduser().resolve())
        return "uv", ["run", "--directory", abs_path, "python", "-m", "dagwood", "mcp"]
    return "dag", ["mcp"]


def json_mcp_servers_builder(command: str, args: list[str]) -> str:
    return json.dumps({"mcpServers": {SERVER_NAME: {"command": command, "args": args}}}, indent=2)


def codex_builder(command: str, args: list[str]) -> str:
    args_repr = "[" + ", ".join(json.dumps(a) for a in args) + "]"
    return f'[mcp_servers.{SERVER_NAME}]\ncommand = "{command}"\nargs    = {args_repr}\n'


def opencode_builder(command: str, args: list[str]) -> str:
    return json.dumps(
        {
            "$schema": "https://opencode.ai/config.json",
            "mcp": {SERVER_NAME: {"type": "local", "command": [command, *args], "enabled": True}},
        },
        indent=2,
    )


def vscode_builder(command: str, args: list[str]) -> str:
    return json.dumps({"servers": {SERVER_NAME: {"type": "stdio", "command": command, "args": args}}}, indent=2)


def zed_builder(command: str, args: list[str]) -> str:
    return json.dumps(
        {"context_servers": {SERVER_NAME: {"source": "custom", "command": command, "args": args, "env": {}}}},
        indent=2,
    )


def run(*, client: str, dev_path: str | None = None) -> int:
    from ._clients import CLIENTS

    rec = CLIENTS.get(client)
    if rec is None:
        known = ", ".join(CLIENTS)
        print(f"unknown client: {client}\nknown clients: {known}", file=sys.stderr)
        return 2
    command, args = command_and_args(dev_path)
    if dev_path is None and shutil.which("dag") is None:
        print(
            "# note: `dag` is not on PATH. install dagwood (e.g. `uv tool install dagwood`) "
            "or re-run with --dev-path /path/to/dagwood.",
            file=sys.stderr,
        )
    print(f"# paste into {rec.hint}\n")
    print(rec.snippet(command, args))
    return 0
