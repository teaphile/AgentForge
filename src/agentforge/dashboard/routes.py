"""Dashboard REST API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class ApprovalRequest(BaseModel):
    approved: bool
    edit: str | None = None
    reason: str | None = None


def create_routes(
    tracer: Any = None,
    approval_manager: Any = None,
    ws_manager: Any = None,
) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/status")
    async def get_status():
        if tracer is None:
            return {"status": "idle", "events": 0}

        events = tracer.get_timeline()
        # Determine status from events
        status = "idle"
        if events:
            last_event = events[-1]
            etype = last_event.get("event_type", "")
            if etype == "workflow_end":
                status = "completed"
            elif etype == "error":
                status = "error"
            elif etype == "approval_requested":
                status = "awaiting_approval"
            else:
                status = "running"

        return {
            "status": status,
            "events_count": len(events),
            "elapsed": tracer.elapsed(),
        }

    @router.get("/trace")
    async def get_trace():
        if tracer is None:
            return {"events": [], "cost_breakdown": {}}
        return {
            "events": tracer.get_timeline(),
            "cost_breakdown": tracer.get_cost_breakdown(),
        }

    @router.get("/costs")
    async def get_costs():
        if tracer is None:
            return {"total_cost": 0, "total_tokens": {"input": 0, "output": 0}}
        return tracer.get_cost_breakdown()

    @router.post("/approve/{step_id}")
    async def approve_step(step_id: str, request: ApprovalRequest):
        if approval_manager is None:
            raise HTTPException(status_code=503, detail="Approval manager not available")

        approval_manager.resolve_approval(
            step_id=step_id,
            approved=request.approved,
            edited_output=request.edit,
            reason=request.reason,
        )
        return {"status": "ok", "step_id": step_id, "approved": request.approved}

    return router
