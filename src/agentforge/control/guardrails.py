"""Safety guardrails for tool usage."""

from __future__ import annotations


class Guardrails:

    def __init__(
        self,
        allowed_actions: list[str] | None = None,
        blocked_actions: list[str] | None = None,
    ):
        self.allowed_actions = allowed_actions or []
        self.blocked_actions = blocked_actions or []

    def is_tool_allowed(self, tool_name: str) -> bool:
        if self.blocked_actions and tool_name in self.blocked_actions:
            return False
        if self.allowed_actions and tool_name not in self.allowed_actions:
            return False
        return True

    def filter_tools(self, tool_names: list[str]) -> list[str]:
        return [t for t in tool_names if self.is_tool_allowed(t)]
