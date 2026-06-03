"""dagwood pure engine.

Imports nothing from the server, MCP, or web layers — the same discipline that
keeps rlaif's safety core MCP-free. This is what lets one engine back the live
server, the MCP tools, the CLI, and the tests with no wiring.
"""

from __future__ import annotations

from .algos import (
    blocked_nodes,
    critical_path,
    detect_cycle,
    frontier,
    is_blocked,
    is_ready,
    topo_sort,
    why_blocked,
)
from .errors import CycleError, DagError, DuplicateId, NodeNotFound, ValidationError
from .graph import add_edge, add_node, remove_edge, remove_node, set_fields, set_status
from .ids import new_id
from .model import STATUSES, Graph, Node, Status
from .toml_io import SCHEMA_VERSION, dump_toml, dumps, load_toml, loads, save_toml

__all__ = [
    # model
    "Node",
    "Graph",
    "Status",
    "STATUSES",
    # errors
    "DagError",
    "ValidationError",
    "NodeNotFound",
    "DuplicateId",
    "CycleError",
    # ids
    "new_id",
    # io
    "load_toml",
    "loads",
    "dump_toml",
    "dumps",
    "save_toml",
    "SCHEMA_VERSION",
    # algos
    "detect_cycle",
    "topo_sort",
    "is_ready",
    "is_blocked",
    "frontier",
    "blocked_nodes",
    "why_blocked",
    "critical_path",
    # graph mutations
    "add_node",
    "remove_node",
    "add_edge",
    "remove_edge",
    "set_status",
    "set_fields",
]
