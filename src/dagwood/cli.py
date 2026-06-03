"""dagwood CLI.

serve  — run the live server
init   — scaffold .dag/ in a repo
doctor — read-only health check (parse / cycle / orphans)
log    — show recent mutations
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__


def _resolve_dag_path(explicit: str | None) -> Path:
    """Find the repo's .dag/dag.toml by walking up from cwd (like git)."""
    if explicit:
        return Path(explicit)
    cwd = Path.cwd()
    for d in (cwd, *cwd.parents):
        candidate = d / ".dag" / "dag.toml"
        if candidate.exists():
            return candidate
    return cwd / ".dag" / "dag.toml"


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .core import toml_io
    from .core.model import Graph
    from .live.app import create_app

    dag_path = _resolve_dag_path(args.path)
    if not dag_path.exists():
        toml_io.save_toml(dag_path, Graph())
    app = create_app(dag_path, watch=not args.no_watch)
    print(f"dagwood: serving {dag_path}")
    print(f"  -> http://{args.host}:{args.port}   (Ctrl-C to stop)")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    from .core import toml_io
    from .core.model import Graph

    dagdir = Path(args.directory) / ".dag"
    dag_file = dagdir / "dag.toml"
    created = not dag_file.exists()
    if created:
        toml_io.save_toml(dag_file, Graph())
    gitignore = dagdir / ".gitignore"
    if not gitignore.exists():
        toml_io.atomic_write_text(
            gitignore,
            "# dagwood: commit dag.toml; ignore local geometry and the ops log\nlayout.json\nops.jsonl\n",
        )
    print(f"{'created' if created else 'already exists'}: {dag_file}")
    print(f"gitignore:        {gitignore} (layout.json, ops.jsonl)")
    print("next:             dag serve")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    from .core import algos, toml_io
    from .core.errors import DagError

    dag_path = _resolve_dag_path(args.path)
    if not dag_path.exists():
        print(f"no dag found at {dag_path} (run `dag init`)", file=sys.stderr)
        return 1
    try:
        g = toml_io.load_toml(dag_path)
    except DagError as e:
        print(f"FAIL  {dag_path}\n      {e}", file=sys.stderr)
        return 1

    by = {"todo": 0, "doing": 0, "done": 0}
    for node in g.nodes.values():
        by[node.status] += 1
    needed: set[str] = set()
    for node in g.nodes.values():
        needed.update(node.needs)
    orphans = [nid for nid, node in g.nodes.items() if not node.needs and nid not in needed]

    print(f"OK    {dag_path}")
    print(f"      {len(g.nodes)} tasks: {by['done']} done · {by['doing']} doing · {by['todo']} todo")
    print(f"      frontier (actionable now): {len(algos.frontier(g))}")
    print(f"      blocked: {len(algos.blocked_nodes(g))}")
    print(f"      longest dependency chain: {len(algos.critical_path(g))}")
    if orphans:
        print(f"      isolated (no deps, no dependents): {len(orphans)}")
    return 0


def _cmd_log(args: argparse.Namespace) -> int:
    from .oplog import tail

    dag_path = _resolve_dag_path(args.path)
    records = tail(dag_path.parent / "ops.jsonl", args.count)
    if not records:
        print("no recorded operations")
        return 0
    for r in records:
        ids = [*r.get("added", []), *r.get("updated", []), *r.get("removed", [])]
        ts = str(r.get("ts", "?"))
        src = str(r.get("source", "?"))
        op = str(r.get("op", "?"))
        print(f"{ts:20} {src:7} {op:12} {' '.join(ids)}")
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

    init = sub.add_parser("init", help="scaffold .dag/ in a repo")
    init.add_argument("directory", nargs="?", default=".", help="repo root (default: cwd)")

    doctor = sub.add_parser("doctor", help="health check (parse / cycle / orphans)")
    doctor.add_argument("--path", default=None, help="path to .dag/dag.toml")

    logp = sub.add_parser("log", help="show recent mutations")
    logp.add_argument("--path", default=None, help="path to .dag/dag.toml")
    logp.add_argument("-n", "--count", type=int, default=20, help="how many to show (default: 20)")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command
    if not command:
        parser.print_help()
        return 0
    if command == "serve":
        return _cmd_serve(args)
    if command == "init":
        return _cmd_init(args)
    if command == "doctor":
        return _cmd_doctor(args)
    if command == "log":
        return _cmd_log(args)
    print(f"unknown command: {command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
