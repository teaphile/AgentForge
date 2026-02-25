"""Tests for built-in tools."""

from __future__ import annotations

import pytest

from agentforge.tools.builtin.calculator import calculator_tool
from agentforge.tools.builtin.python_executor import python_exec_tool
from agentforge.tools.builtin.file_ops import file_read_tool, file_write_tool


class TestCalculator:
    @pytest.mark.asyncio
    async def test_basic_math(self):
        result = await calculator_tool.execute(expression="2 + 2")
        assert result.success is True
        assert "4" in result.output

    @pytest.mark.asyncio
    async def test_complex_expression(self):
        result = await calculator_tool.execute(expression="(10 * 5) + 3")
        assert result.success is True
        assert "53" in result.output

    @pytest.mark.asyncio
    async def test_invalid_expression(self):
        result = await calculator_tool.execute(expression="import os")
        # Calculator may return success=True with an error in output, or success=False
        assert "error" in result.output.lower() or result.success is False


class TestPythonExecutor:
    @pytest.mark.asyncio
    async def test_simple_code(self):
        result = await python_exec_tool.execute(code="print(1 + 1)")
        assert result.success is True
        assert "2" in result.output

    @pytest.mark.asyncio
    async def test_syntax_error(self):
        result = await python_exec_tool.execute(code="def f(:")
        # May return success=True with error info, or success=False
        assert "error" in result.output.lower() or result.success is False


class TestFileOps:
    @pytest.mark.asyncio
    async def test_write_and_read(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENTFORGE_FILE_SANDBOX", str(tmp_path))

        test_file = str(tmp_path / "test.txt")
        write_result = await file_write_tool.execute(path=test_file, content="Hello World")
        assert write_result.success is True

        read_result = await file_read_tool.execute(path=test_file)
        assert read_result.success is True
        assert "Hello World" in read_result.output

    @pytest.mark.asyncio
    async def test_read_nonexistent(self):
        result = await file_read_tool.execute(path="/nonexistent/file.txt")
        assert (
            result.success is False
            or "error" in result.output.lower()
            or "not found" in result.output.lower()
        )
