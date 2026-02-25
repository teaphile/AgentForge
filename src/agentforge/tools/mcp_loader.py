"""Placeholder for MCP (Model Context Protocol) tool loading."""

from __future__ import annotations

from agentforge.tools.base import Tool


class MCPLoader:

    def __init__(self):
        self._servers: dict[str, dict] = {}

    def register_server(self, name: str, config: dict):
        self._servers[name] = config

    async def load_tools(self, server_name: str) -> list[Tool]:
        # Not yet implemented
        return []
