"""Registry of MCP clients dagwood can configure.

One entry per client. fmt drives auto-install: "json" (an mcpServers JSON
config), "toml" (codex), or "none" (snippet-only). Iteration order is the
order shown to operators.

Imports flow leaf-ward: this imports the builders from snippet; installer and
snippet defer their import of CLIENTS to call time to keep it acyclic.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .snippet import (
    Builder,
    codex_builder,
    json_mcp_servers_builder,
    opencode_builder,
    vscode_builder,
    zed_builder,
)


@dataclass(frozen=True)
class Client:
    name: str
    hint: str
    fmt: str  # "json" | "toml" | "none"
    path_fn: Callable[[], Path] | None
    snippet: Builder


def _claude_desktop_path() -> Path:
    return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"


def _records() -> tuple[Client, ...]:
    return (
        Client(
            "claude-code",
            "~/.claude.json (user) or .claude.json (project)",
            "json",
            lambda: Path.home() / ".claude.json",
            json_mcp_servers_builder,
        ),
        Client(
            "codex",
            "~/.codex/config.toml",
            "toml",
            lambda: Path.home() / ".codex" / "config.toml",
            codex_builder,
        ),
        Client(
            "claude-desktop",
            "~/Library/Application Support/Claude/claude_desktop_config.json",
            "json",
            _claude_desktop_path,
            json_mcp_servers_builder,
        ),
        Client(
            "cursor",
            "~/.cursor/mcp.json (user) or .cursor/mcp.json (project)",
            "json",
            lambda: Path.home() / ".cursor" / "mcp.json",
            json_mcp_servers_builder,
        ),
        Client(
            "windsurf",
            "~/.codeium/windsurf/mcp_config.json",
            "json",
            lambda: Path.home() / ".codeium" / "windsurf" / "mcp_config.json",
            json_mcp_servers_builder,
        ),
        Client(
            "opencode",
            "opencode.json (project) or ~/.config/opencode/opencode.json — snippet only",
            "none",
            None,
            opencode_builder,
        ),
        Client(
            "vscode",
            ".vscode/mcp.json (workspace) — snippet only",
            "none",
            None,
            vscode_builder,
        ),
        Client(
            "zed",
            "~/.config/zed/settings.json (merge fragment) — snippet only",
            "none",
            None,
            zed_builder,
        ),
    )


CLIENTS: dict[str, Client] = {c.name: c for c in _records()}
INSTALLABLE: tuple[str, ...] = tuple(name for name, c in CLIENTS.items() if c.fmt != "none")
