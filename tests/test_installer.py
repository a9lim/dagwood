import json
import tomllib
from pathlib import Path

from dagwood import installer, snippet


def test_install_json_fresh(tmp_path: Path):
    cfg = tmp_path / "claude.json"
    assert installer._install_json(cfg, "dag", ["mcp"], dry_run=False, force=False) == 0
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["mcpServers"]["dagwood"] == {"command": "dag", "args": ["mcp"]}


def test_install_json_idempotent(tmp_path: Path):
    cfg = tmp_path / "claude.json"
    installer._install_json(cfg, "dag", ["mcp"], dry_run=False, force=False)
    assert installer._install_json(cfg, "dag", ["mcp"], dry_run=False, force=False) == 0  # already installed


def test_install_json_preserves_others(tmp_path: Path):
    cfg = tmp_path / "claude.json"
    cfg.write_text(json.dumps({"mcpServers": {"other": {"command": "x", "args": []}}, "keep": 1}), encoding="utf-8")
    installer._install_json(cfg, "dag", ["mcp"], dry_run=False, force=False)
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert "other" in data["mcpServers"] and "dagwood" in data["mcpServers"]
    assert data["keep"] == 1


def test_install_json_refuses_conflict_then_force(tmp_path: Path):
    cfg = tmp_path / "claude.json"
    cfg.write_text(json.dumps({"mcpServers": {"dagwood": {"command": "old", "args": []}}}), encoding="utf-8")
    assert installer._install_json(cfg, "dag", ["mcp"], dry_run=False, force=False) == 1
    assert installer._install_json(cfg, "dag", ["mcp"], dry_run=False, force=True) == 0
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["mcpServers"]["dagwood"]["command"] == "dag"


def test_install_json_dry_run_writes_nothing(tmp_path: Path):
    cfg = tmp_path / "claude.json"
    assert installer._install_json(cfg, "dag", ["mcp"], dry_run=True, force=False) == 0
    assert not cfg.exists()


def test_install_toml_codex(tmp_path: Path):
    cfg = tmp_path / "config.toml"
    assert installer._install_toml(cfg, "dag", ["mcp"], dry_run=False, force=False) == 0
    data = tomllib.loads(cfg.read_text(encoding="utf-8"))
    assert data["mcp_servers"]["dagwood"]["command"] == "dag"
    assert data["mcp_servers"]["dagwood"]["args"] == ["mcp"]


def test_install_toml_preserves_existing(tmp_path: Path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('model = "gpt-5"\n\n[mcp_servers.other]\ncommand = "x"\nargs = []\n', encoding="utf-8")
    installer._install_toml(cfg, "dag", ["mcp"], dry_run=False, force=False)
    data = tomllib.loads(cfg.read_text(encoding="utf-8"))
    assert data["model"] == "gpt-5"
    assert "other" in data["mcp_servers"] and "dagwood" in data["mcp_servers"]


def test_snippet_known_client(capsys):
    assert snippet.run(client="claude-code") == 0
    out = capsys.readouterr().out
    assert "mcpServers" in out and "dagwood" in out


def test_snippet_codex(capsys):
    assert snippet.run(client="codex") == 0
    assert "[mcp_servers.dagwood]" in capsys.readouterr().out


def test_snippet_unknown_client():
    assert snippet.run(client="nope") == 2


def test_install_unknown_client():
    assert installer.install("nope") == 2
