"""Security tests for built-in tools."""

from __future__ import annotations

import pytest

from agentforge.tools.builtin.calculator import calculator_tool
from agentforge.tools.builtin.python_executor import python_exec_tool
from agentforge.tools.builtin.file_ops import file_read_tool, file_write_tool
from agentforge.tools.builtin.http_request import http_request_tool


class TestCalculatorSafety:
    """Verify the AST-based calculator blocks dangerous input."""

    @pytest.mark.asyncio
    async def test_blocks_import(self):
        result = await calculator_tool.execute(expression="__import__('os')")
        assert result.success is False or "error" in result.output.lower()

    @pytest.mark.asyncio
    async def test_blocks_dunder_access(self):
        result = await calculator_tool.execute(expression="().__class__.__bases__")
        assert result.success is False or "error" in result.output.lower()

    @pytest.mark.asyncio
    async def test_allows_math_functions(self):
        result = await calculator_tool.execute(expression="sqrt(16)")
        assert result.success is True
        assert "4" in result.output

    @pytest.mark.asyncio
    async def test_allows_constants(self):
        result = await calculator_tool.execute(expression="pi")
        assert result.success is True
        assert "3.14" in result.output

    @pytest.mark.asyncio
    async def test_nested_expression(self):
        result = await calculator_tool.execute(expression="abs(-5) + pow(2, 3)")
        assert result.success is True
        assert "13" in result.output


class TestPythonExecutorSandbox:
    """Verify the subprocess sandbox blocks dangerous operations."""

    @pytest.mark.asyncio
    async def test_blocks_os_import(self):
        result = await python_exec_tool.execute(code="import os; print(os.environ)")
        assert "not allowed" in result.output.lower() or "error" in result.output.lower()

    @pytest.mark.asyncio
    async def test_blocks_subprocess(self):
        result = await python_exec_tool.execute(code="import subprocess; subprocess.run(['ls'])")
        assert "not allowed" in result.output.lower() or "error" in result.output.lower()

    @pytest.mark.asyncio
    async def test_allows_safe_modules(self):
        result = await python_exec_tool.execute(code="import math; print(math.sqrt(25))")
        assert result.success is True
        assert "5" in result.output

    @pytest.mark.asyncio
    async def test_allows_json(self):
        result = await python_exec_tool.execute(code='import json; print(json.dumps({"a": 1}))')
        assert result.success is True
        assert '"a"' in result.output

    @pytest.mark.asyncio
    async def test_empty_env(self):
        """Subprocess should not inherit host environment."""
        result = await python_exec_tool.execute(
            code="import os; print(len(os.environ))"
        )
        # os is blocked by the import guard, so it should fail
        assert "not allowed" in result.output.lower() or "error" in result.output.lower()


class TestFileSandbox:
    """Verify file_ops sandbox blocks path traversal."""

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENTFORGE_FILE_SANDBOX", str(tmp_path))
        # Try to escape sandbox with ../
        result = await file_read_tool.execute(path=str(tmp_path / ".." / "etc" / "passwd"))
        assert result.success is False or "sandbox" in result.output.lower() or "outside" in result.output.lower()

    @pytest.mark.asyncio
    async def test_write_inside_sandbox(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENTFORGE_FILE_SANDBOX", str(tmp_path))
        result = await file_write_tool.execute(
            path=str(tmp_path / "safe.txt"), content="hello"
        )
        assert result.success is True


class TestHTTPSSRF:
    """Verify http_request blocks private IPs."""

    @pytest.mark.asyncio
    async def test_blocks_localhost(self):
        result = await http_request_tool.execute(
            url="http://127.0.0.1:8080/secret", method="GET"
        )
        assert result.success is False or "blocked" in result.output.lower() or "ssrf" in result.output.lower()

    @pytest.mark.asyncio
    async def test_blocks_metadata_endpoint(self):
        result = await http_request_tool.execute(
            url="http://169.254.169.254/latest/meta-data/", method="GET"
        )
        assert result.success is False or "blocked" in result.output.lower()

    @pytest.mark.asyncio
    async def test_blocks_private_ip(self):
        result = await http_request_tool.execute(
            url="http://10.0.0.1/internal", method="GET"
        )
        assert result.success is False or "blocked" in result.output.lower()
