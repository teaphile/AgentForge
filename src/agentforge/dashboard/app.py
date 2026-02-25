"""FastAPI dashboard for real-time execution monitoring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from agentforge.dashboard.routes import create_routes
from agentforge.dashboard.ws import WebSocketManager, create_ws_router


def create_dashboard_app(
    event_bus: Any = None,
    tracer: Any = None,
    approval_manager: Any = None,
) -> FastAPI:
    app = FastAPI(
        title="AgentForge Dashboard",
        description="Real-time multi-agent execution monitoring",
        version="0.1.0",
    )

    # WebSocket manager for real-time updates
    ws_manager = WebSocketManager()

    # Connect event bus to WebSocket broadcaster
    if event_bus is not None:
        async def broadcast_event(event: Any):
            await ws_manager.broadcast(event.to_dict())

        event_bus.subscribe(broadcast_event)

    # Register REST routes
    router = create_routes(tracer=tracer, approval_manager=approval_manager, ws_manager=ws_manager)
    app.include_router(router)

    # Register WebSocket route
    ws_router = create_ws_router(ws_manager, approval_manager=approval_manager)
    app.include_router(ws_router)

    # Serve static files
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Root → serve index.html
    @app.get("/", response_class=HTMLResponse)
    async def root():
        index_path = static_dir / "index.html"
        if index_path.exists():
            return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
        return HTMLResponse(content="<h1>AgentForge Dashboard</h1><p>Static files not found.</p>")

    return app
