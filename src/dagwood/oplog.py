"""Append-only JSONL audit of graph mutations (per repo, at .dag/ops.jsonl).

One record per mutation. The live server writes it; `dag log` reads it; the
MCP layer (M6) will write to the same log. Gitignored by `dag init`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast


def append(path: str | os.PathLike[str], record: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")
        f.flush()
        os.fsync(f.fileno())


def tail(path: str | os.PathLike[str], n: int = 20) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-n:] if n >= 0 else lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(cast("dict[str, Any]", rec))
    return out
