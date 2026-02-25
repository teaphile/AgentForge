"""Tool base classes and the @tool decorator."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Callable, get_type_hints


@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None


class Tool:
    """
    A callable tool exposed to agents.

    Attributes:
        name: unique tool name (snake_case)
        description: shown to the LLM
        parameters: JSON Schema for arguments
        handler: async callable
    """

    def __init__(self, name: str, description: str, parameters: dict, handler: Callable):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler

    async def execute(self, **kwargs) -> ToolResult:
        try:
            if asyncio.iscoroutinefunction(self.handler):
                result = await self.handler(**kwargs)
            else:
                result = self.handler(**kwargs)
            return ToolResult(success=True, output=str(result))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"{type(e).__name__}: {e}")

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# Type mapping from Python type annotations to JSON Schema types
_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _build_parameters_schema(func: Callable) -> dict:
    """Build JSON Schema parameters from function signature and type hints."""
    sig = inspect.signature(func)
    hints = get_type_hints(func) if hasattr(func, "__annotations__") else {}

    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue

        param_type = hints.get(param_name, str)
        json_type = _TYPE_MAP.get(param_type, "string")

        prop: dict[str, Any] = {"type": json_type}

        # Use docstring or param name as description
        prop["description"] = param_name.replace("_", " ").title()

        if param.default is not inspect.Parameter.empty:
            prop["default"] = param.default
        else:
            required.append(param_name)

        properties[param_name] = prop

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def tool(name: str | None = None, description: str = ""):
    """
    Decorator to create tools from simple functions.

    Usage:
        @tool(description="Search the web for information")
        async def web_search(query: str) -> str:
            ...
            return results
    """

    def decorator(func: Callable) -> Tool:
        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or f"Tool: {tool_name}"
        params = _build_parameters_schema(func)
        return Tool(name=tool_name, description=tool_desc, parameters=params, handler=func)

    return decorator
