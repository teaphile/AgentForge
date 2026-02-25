"""Tool registry mapping tool name strings to Tool instances."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

from agentforge.tools.base import Tool

_log = logging.getLogger(__name__)


class ToolRegistry:

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._builtin_loaded = False

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        if not self._builtin_loaded:
            self._load_builtins()
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        if not self._builtin_loaded:
            self._load_builtins()
        return list(self._tools.keys())

    def _load_builtins(self):
        """Lazy-load all built-in tools."""
        if self._builtin_loaded:
            return
        self._builtin_loaded = True

        try:
            from agentforge.tools.builtin.web_search import web_search_tool

            self.register(web_search_tool)
        except ImportError:
            pass

        try:
            from agentforge.tools.builtin.file_ops import file_read_tool, file_write_tool

            self.register(file_read_tool)
            self.register(file_write_tool)
        except ImportError:
            pass

        try:
            from agentforge.tools.builtin.http_request import http_request_tool

            self.register(http_request_tool)
        except ImportError:
            pass

        try:
            from agentforge.tools.builtin.calculator import calculator_tool

            self.register(calculator_tool)
        except ImportError:
            pass

        try:
            from agentforge.tools.builtin.python_executor import python_exec_tool

            self.register(python_exec_tool)
        except ImportError:
            pass

    def resolve_tools(self, tool_specs: list[str]) -> list[Tool]:
        if not self._builtin_loaded:
            self._load_builtins()

        resolved = []
        for spec in tool_specs:
            if spec.startswith("mcp:"):
                _log.debug("MCP tool '%s' skipped (not yet supported)", spec)
                continue
            elif spec.startswith("custom:"):
                custom_path = spec[7:]  # strip "custom:"
                custom_tool = self._load_custom_tool(custom_path)
                if custom_tool:
                    resolved.append(custom_tool)
            else:
                tool = self.get(spec)
                if tool:
                    resolved.append(tool)

        return resolved

    def _load_custom_tool(self, path: str) -> Tool | None:
        try:
            file_path = Path(path)
            if not file_path.exists():
                return None

            spec = importlib.util.spec_from_file_location("custom_tool", file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Look for Tool instances in the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, Tool):
                        self.register(attr)
                        return attr
        except Exception as exc:
            _log.warning("Failed to load custom tool from '%s': %s", path, exc)
        return None


# Global registry instance
_global_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    return _global_registry
