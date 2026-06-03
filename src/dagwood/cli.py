"""dagwood CLI entrypoint.

`dag serve` runs the live server (M2). `init`/`doctor` land in M5; the
MCP/install verbs in M6.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__


def _resolve_dag_path(explicit: str | None) -> Path:
    """Find the repo's .dag/dag.toml by walking up from cwd (like git). If none
    exists, default to ./.dag/dag.toml and create an empty one."""
    if explicit:
        return Path(explicit)
    cwd = Path.cwd()
    for d in (cwd, *cwd.parents):
        candidate = d / ".dag" / "dag.toml"
        if candidate.exists():
            return candidate
    default = cwd / ".dag" / "dag.toml"
    if not default.exists():
        from .core import toml_io
        from .core.model import Graph

        toml_io.save_toml(default, Graph())
    return default


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .live.app import create_app

    dag_path = _resolve_dag_path(args.path)
    app = create_app(dag_path, watch=not args.no_watch)
    print(f"dagwood: serving {dag_path}")
    print(f"  -> http://{args.host}:{args.port}   (Ctrl-C to stop)")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dag", description="dagwood — a DAG-native task tracker")
    parser.add_argument("--version", action="version", version=f"dagwood {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    serve = sub.add_parser("serve", help="run the live server")
    serve.add_argument("--path", default=None, help="path to .dag/dag.toml (default: search up from cwd)")
    serve.add_argument("--host", default="127.0.0.1", help="bind host (default: 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8765, help="bind port (default: 8765)")
    serve.add_argument("--no-watch", action="store_true", help="disable filesystem watching")

    sub.add_parser("init", help="scaffold .dag/ in a repo (M5)")
    sub.add_parser("doctor", help="parse/cycle/orphan health check (M5)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    if args.command == "serve":
        return _cmd_serve(args)
    print(f"dag {args.command}: not implemented yet (scaffolding in progress)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
