"""Dry-run mode: simulate tool executions without side effects."""

from __future__ import annotations

from agentforge.tools.base import ToolResult


class DryRunController:

    def __init__(self, enabled: bool = False):
        self.enabled = enabled

    def simulate_tool(self, tool_name: str, arguments: dict) -> ToolResult:
        args_str = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
        simulated_output = (
            f"[DRY RUN] Would call {tool_name}({args_str})\n"
            f"Simulated result: Tool '{tool_name}' executed successfully with provided arguments."
        )
        return ToolResult(success=True, output=simulated_output)
