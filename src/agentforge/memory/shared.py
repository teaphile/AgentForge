"""Shared memory pool accessible by all agents in a team."""

from __future__ import annotations

from agentforge.memory.base import BaseMemory
from agentforge.memory.short_term import ShortTermMemory
from agentforge.memory.long_term import LongTermMemory


class SharedMemory:

    def __init__(self, backend: BaseMemory):
        self.backend = backend

    async def store(self, agent_name: str, content: str, importance: float = 0.5, metadata: dict | None = None) -> str:
        return await self.backend.store(agent_name, content, importance, metadata)

    async def recall(self, agent_name: str, query: str, limit: int = 5) -> list[dict]:
        return await self.backend.recall(agent_name, query, limit)

    async def clear(self, agent_name: str | None = None):
        await self.backend.clear(agent_name)


def create_memory(config: dict) -> BaseMemory | None:
    if not config.get("enabled", True):
        return None

    backend = config.get("backend", "sqlite")
    path = config.get("path", ".agentforge/memory.db")
    shared = config.get("shared", True)

    if backend == "sqlite" or backend == "chromadb":
        return LongTermMemory(db_path=path, shared=shared)
    else:
        return ShortTermMemory(shared=shared)
