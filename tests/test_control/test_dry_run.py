"""Tests for dry run controller."""

from __future__ import annotations


from agentforge.control.dry_run import DryRunController
from agentforge.tools.base import ToolResult


class TestDryRunController:
    def test_init_enabled(self):
        ctrl = DryRunController(enabled=True)
        assert ctrl.enabled is True

    def test_init_disabled(self):
        ctrl = DryRunController(enabled=False)
        assert ctrl.enabled is False

    def test_default_disabled(self):
        ctrl = DryRunController()
        assert ctrl.enabled is False

    def test_simulate_tool(self):
        ctrl = DryRunController(enabled=True)
        result = ctrl.simulate_tool("web_search", {"query": "test"})
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "DRY RUN" in result.output
        assert "web_search" in result.output

    def test_simulate_tool_includes_args(self):
        ctrl = DryRunController(enabled=True)
        result = ctrl.simulate_tool("calculator", {"expression": "2+2"})
        assert "2+2" in result.output
