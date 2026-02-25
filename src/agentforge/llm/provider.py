"""LLM response types and error classes."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[dict] = field(default_factory=list)
    model_used: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    latency_ms: float = 0.0


class LLMError(Exception):

    def __init__(self, message: str, models_tried: list[str] = None, errors: list[str] = None):
        self.models_tried = models_tried or []
        self.errors = errors or []
        super().__init__(message)
