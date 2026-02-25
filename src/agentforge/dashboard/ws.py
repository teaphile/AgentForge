"""WebSocket manager for real-time event streaming."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


class WebSocketManager:

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        message = json.dumps(data, default=str)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


def create_ws_router(ws_manager: WebSocketManager, approval_manager: Any = None) -> APIRouter:
    router = APIRouter()

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await ws_manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    parsed = json.loads(data)
                    if parsed.get("type") == "approval" and approval_manager is not None:
                        approval_manager.resolve_approval(
                            step_id=parsed.get("step_id", ""),
                            approved=parsed.get("approved", True),
                            edited_output=parsed.get("edit"),
                            reason=parsed.get("reason"),
                        )
                except json.JSONDecodeError:
                    pass
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    return router
