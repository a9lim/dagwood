"""Starlette app factory wiring the store to HTTP + websocket.

The file is the source of truth; this server is its only writer. Mutations from
the canvas (ws) and CLI/MCP (POST /api/mutate) both funnel through the store and
fan out to all connected clients as patches.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import BaseRoute, Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

from . import protocol
from .layout import from_dict as layout_from_dict
from .layout import layout_to_dict, save_layout
from .store import MutationError, Store

STATIC_DIR = Path(__file__).parent / "static"
LAYOUT_TYPES = frozenset({"set_layout", "set_viewport"})

_PLACEHOLDER = """<!doctype html><html><head><meta charset="utf-8"><title>dagwood</title></head>
<body style="font-family:system-ui;max-width:40rem;margin:3rem auto;line-height:1.5">
<h1>dagwood server is running</h1>
<p>The live canvas ships in milestone M3. For now the API is live:</p>
<ul>
<li><code>GET /api/graph</code> — current snapshot</li>
<li><code>GET /healthz</code> — health</li>
<li><code>WS /ws</code> — live channel (snapshot, then patches)</li>
</ul></body></html>"""


def _safe_op_id(data: Any) -> str | None:
    try:
        v = data.get("op_id")
    except AttributeError:
        return None
    return v if isinstance(v, str) else None


def _handle_ws(store: Store, q: asyncio.Queue[dict[str, Any]], data: Any) -> None:
    """Apply one client message. Patches broadcast to all; errors go to the
    originator only."""
    op_id = _safe_op_id(data)
    t = data.get("type") if hasattr(data, "get") else None
    try:
        if t in LAYOUT_TYPES:
            store.handle_layout(data)
            return
        patch = store.apply_mutation(data, op_id=op_id)
    except MutationError as e:
        q.put_nowait(protocol.error_msg(e.code, e.message, op_id=op_id))
        return
    store.broadcast(patch)


def create_app(
    dag_path: str | Path,
    layout_path: str | Path | None = None,
    *,
    watch: bool = True,
) -> Starlette:
    dag_p = Path(dag_path)
    layout_p = Path(layout_path) if layout_path is not None else dag_p.parent / "layout.json"
    store = Store(dag_p, layout_p)

    async def graph_endpoint(request: Request) -> Response:
        return JSONResponse(store.snapshot())

    async def health_endpoint(request: Request) -> Response:
        return JSONResponse({"parse_ok": True, "nodes": len(store.graph.nodes), "cycle": None})

    async def layout_endpoint(request: Request) -> Response:
        if request.method == "PUT":
            body: Any = await request.json()
            store.layout = layout_from_dict(body)
            save_layout(store.layout_path, store.layout)
        return JSONResponse(layout_to_dict(store.layout))

    async def mutate_endpoint(request: Request) -> Response:
        body: Any = await request.json()
        try:
            patch = store.apply_mutation(body, op_id=_safe_op_id(body))
        except MutationError as e:
            return JSONResponse(protocol.error_msg(e.code, e.message), status_code=400)
        store.broadcast(patch)
        return JSONResponse(patch)

    async def placeholder_endpoint(request: Request) -> Response:
        return HTMLResponse(_PLACEHOLDER)

    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        q = store.subscribe()
        await websocket.send_json(store.snapshot())

        async def sender() -> None:
            with contextlib.suppress(Exception):
                while True:
                    await websocket.send_json(await q.get())

        sender_task = asyncio.create_task(sender())
        try:
            while True:
                data: Any = await websocket.receive_json()
                _handle_ws(store, q, data)
        except WebSocketDisconnect:
            pass
        finally:
            sender_task.cancel()
            store.unsubscribe(q)
            with contextlib.suppress(BaseException):
                await sender_task

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncGenerator[None, None]:
        task: asyncio.Task[None] | None = None
        if watch:
            from . import watcher

            task = asyncio.create_task(watcher.run(store))
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    routes: list[BaseRoute] = [
        Route("/api/graph", graph_endpoint),
        Route("/api/layout", layout_endpoint, methods=["GET", "PUT"]),
        Route("/api/mutate", mutate_endpoint, methods=["POST"]),
        Route("/healthz", health_endpoint),
        WebSocketRoute("/ws", ws_endpoint),
    ]
    if STATIC_DIR.exists():
        routes.append(Mount("/", app=StaticFiles(directory=str(STATIC_DIR), html=True), name="static"))
    else:
        routes.append(Route("/", placeholder_endpoint))

    return Starlette(routes=routes, lifespan=lifespan)
