"""Tests for tool base classes and decorator."""

from __future__ import annotations

import pytest

from agentforge.tools.base import Tool, ToolResult, tool


class TestTool:
    def test_basic_tool(self, sample_tool):
        assert sample_tool.name == "test_tool"
        assert sample_tool.description == "A test tool"

    @pytest.mark.asyncio
    async def test_tool_execute(self, sample_tool):
        result = await sample_tool.execute(query="hello")
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "hello" in result.output

    @pytest.mark.asyncio
    async def test_tool_execute_error(self):
        async def bad_handler(**kwargs):
            raise ValueError("Something broke")

        t = Tool(
            name="bad_tool",
            description="A tool that fails",
            parameters={"type": "object", "properties": {}},
            handler=bad_handler,
        )
        result = await t.execute()
        assert result.success is False
        assert "Something broke" in result.error

    def test_to_openai_schema(self, sample_tool):
        schema = sample_tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "test_tool"
        assert "parameters" in schema["function"]


class TestToolDecorator:
    def test_basic_decorator(self):
        @tool(name="greet", description="Greet someone")
        async def greet(name: str) -> str:
            """Greet a person by name."""
            return f"Hello, {name}!"

        assert isinstance(greet, Tool)
        assert greet.name == "greet"

    def test_decorator_auto_schema(self):
        @tool(name="add", description="Add numbers")
        async def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        schema = add.to_openai_schema()
        params = schema["function"]["parameters"]
        assert "a" in params.get("properties", {})
        assert "b" in params.get("properties", {})

    @pytest.mark.asyncio
    async def test_decorated_tool_execute(self):
        @tool(name="double", description="Double a number")
        async def double(n: int) -> str:
            return str(n * 2)

        result = await double.execute(n=5)
        assert result.success is True
        assert "10" in result.output
