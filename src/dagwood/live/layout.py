"""Canvas geometry sidecar (.dag/layout.json) — kept OUT of the semantic file.

Positions are keyed by stable node id so they survive title/status edits. This
file is gitignored by default (see `dag init`), so a drag never dirties the
committed dag.toml diff.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from ..core.toml_io import atomic_write_text


def _empty_overrides() -> dict[str, dict[str, float]]:
    return {}


@dataclass
class Layout:
    overrides: dict[str, dict[str, float]] = field(default_factory=_empty_overrides)
    viewport: dict[str, float] | None = None


def from_dict(data: Any) -> Layout:
    if not isinstance(data, dict):
        return Layout()
    d = cast("dict[str, Any]", data)

    overrides: dict[str, dict[str, float]] = {}
    raw = d.get("overrides", {})
    if isinstance(raw, dict):
        for key, val in cast("dict[Any, Any]", raw).items():
            if isinstance(val, dict):
                vv = cast("dict[str, Any]", val)
                if "x" in vv and "y" in vv:
                    try:
                        overrides[str(key)] = {"x": float(vv["x"]), "y": float(vv["y"])}
                    except (TypeError, ValueError):
                        continue

    viewport: dict[str, float] | None = None
    vp = d.get("viewport")
    if isinstance(vp, dict):
        vpp = cast("dict[str, Any]", vp)
        try:
            viewport = {
                "x": float(vpp.get("x", 0.0)),
                "y": float(vpp.get("y", 0.0)),
                "zoom": float(vpp.get("zoom", 1.0)),
            }
        except (TypeError, ValueError):
            viewport = None

    return Layout(overrides=overrides, viewport=viewport)


def load_layout(path: str | Path) -> Layout:
    p = Path(path)
    if not p.exists():
        return Layout()
    try:
        return from_dict(json.loads(p.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return Layout()


def layout_to_dict(layout: Layout) -> dict[str, Any]:
    out: dict[str, Any] = {"version": 1, "overrides": layout.overrides}
    if layout.viewport is not None:
        out["viewport"] = layout.viewport
    return out


def save_layout(path: str | Path, layout: Layout) -> None:
    atomic_write_text(path, json.dumps(layout_to_dict(layout), indent=2, sort_keys=True) + "\n")
