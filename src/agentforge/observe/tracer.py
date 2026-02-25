"""Execution tracing for observability and replay."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class EventType(str, Enum):
    WORKFLOW_START = "workflow_start"
    WORKFLOW_END = "workflow_end"
    STEP_START = "step_start"
    STEP_END = "step_end"
    AGENT_THINKING = "agent_thinking"
    AGENT_RESPONSE = "agent_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    MEMORY_RECALL = "memory_recall"
    MEMORY_STORE = "memory_store"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RECEIVED = "approval_received"
    ERROR = "error"
    RETRY = "retry"


@dataclass
class TraceEvent:
    event_type: EventType
    timestamp: float = field(default_factory=time.time)
    step_id: str = ""
    agent_name: str = ""
    data: dict = field(default_factory=dict)
    tokens: dict = field(default_factory=dict)
    cost: float = 0.0
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "step_id": self.step_id,
            "agent_name": self.agent_name,
            "data": self.data,
            "tokens": self.tokens,
            "cost": self.cost,
            "duration_ms": self.duration_ms,
        }


class Tracer:

    def __init__(self):
        self.events: list[TraceEvent] = []
        self.start_time: float = 0.0
        self._lock = threading.Lock()

    def record(self, event: TraceEvent):
        with self._lock:
            self.events.append(event)

    def start(self):
        self.start_time = time.time()

    def elapsed(self) -> float:
        if self.start_time:
            return time.time() - self.start_time
        return 0.0

    def get_timeline(self) -> list[dict]:
        return [e.to_dict() for e in self.events]

    def get_cost_breakdown(self) -> dict:
        total_cost = 0.0
        total_input = 0
        total_output = 0
        by_agent: dict[str, dict] = {}
        by_model: dict[str, dict] = {}
        by_step: dict[str, dict] = {}

        for e in self.events:
            if e.cost <= 0 and not e.tokens:
                continue

            total_cost += e.cost
            inp = e.tokens.get("input", 0)
            out = e.tokens.get("output", 0)
            total_input += inp
            total_output += out

            model = e.data.get("model", "unknown")

            if e.agent_name:
                if e.agent_name not in by_agent:
                    by_agent[e.agent_name] = {"cost": 0.0, "tokens": {"input": 0, "output": 0}}
                by_agent[e.agent_name]["cost"] += e.cost
                by_agent[e.agent_name]["tokens"]["input"] += inp
                by_agent[e.agent_name]["tokens"]["output"] += out

            if model != "unknown":
                if model not in by_model:
                    by_model[model] = {"cost": 0.0, "tokens": {"input": 0, "output": 0}}
                by_model[model]["cost"] += e.cost
                by_model[model]["tokens"]["input"] += inp
                by_model[model]["tokens"]["output"] += out

            if e.step_id:
                if e.step_id not in by_step:
                    by_step[e.step_id] = {"cost": 0.0, "tokens": {"input": 0, "output": 0}}
                by_step[e.step_id]["cost"] += e.cost
                by_step[e.step_id]["tokens"]["input"] += inp
                by_step[e.step_id]["tokens"]["output"] += out

        return {
            "total_cost": total_cost,
            "total_tokens": {"input": total_input, "output": total_output},
            "by_agent": by_agent,
            "by_model": by_model,
            "by_step": by_step,
        }

    def export_json(self, path: str):
        data = {
            "start_time": self.start_time,
            "duration": self.elapsed(),
            "events": self.get_timeline(),
            "cost_breakdown": self.get_cost_breakdown(),
        }
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(data, indent=2, default=str))
