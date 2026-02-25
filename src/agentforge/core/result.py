"""Result data classes for workflow execution."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class ToolCallRecord:
    tool_name: str
    arguments: dict
    result: str
    success: bool
    duration_ms: float = 0.0


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class CostSummary:
    total_cost: float = 0.0
    total_tokens: TokenUsage = field(default_factory=TokenUsage)
    by_agent: dict = field(default_factory=dict)
    by_model: dict = field(default_factory=dict)
    by_step: dict = field(default_factory=dict)


@dataclass
class StepResult:
    step_id: str
    agent_name: str
    output: str
    success: bool = True
    tokens: TokenUsage = field(default_factory=TokenUsage)
    cost: float = 0.0
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    iterations: int = 1
    duration: float = 0.0
    model_used: str = ""
    error: str | None = None
    approved: bool | None = None  # None = no approval gate


@dataclass
class AgentResult:
    output: str
    success: bool = True
    tokens: TokenUsage = field(default_factory=TokenUsage)
    cost: float = 0.0
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    iterations: int = 1
    duration: float = 0.0
    model_used: str = ""
    error: str | None = None


@dataclass
class ForgeResult:
    output: str
    steps: list[StepResult] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    cost: CostSummary = field(default_factory=CostSummary)
    duration: float = 0.0
    success: bool = True
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "output": self.output,
            "success": self.success,
            "duration": self.duration,
            "error": self.error,
            "cost": {
                "total_cost": self.cost.total_cost,
                "total_tokens": {
                    "input": self.cost.total_tokens.input_tokens,
                    "output": self.cost.total_tokens.output_tokens,
                    "total": self.cost.total_tokens.total,
                },
                "by_agent": self.cost.by_agent,
                "by_model": self.cost.by_model,
                "by_step": self.cost.by_step,
            },
            "steps": [
                {
                    "step_id": s.step_id,
                    "agent_name": s.agent_name,
                    "output": s.output,
                    "success": s.success,
                    "cost": s.cost,
                    "tokens": {"input": s.tokens.input_tokens, "output": s.tokens.output_tokens},
                    "iterations": s.iterations,
                    "duration": s.duration,
                    "model_used": s.model_used,
                    "error": s.error,
                }
                for s in self.steps
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
