"""Abstract base for memory backends."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseMemory(ABC):

    @abstractmethod
    async def store(self, agent_name: str, content: str, importance: float = 0.5, metadata: dict | None = None) -> str:
        ...

    @abstractmethod
    async def recall(self, agent_name: str, query: str, limit: int = 5) -> list[dict]:
        ...

    @abstractmethod
    async def clear(self, agent_name: str | None = None):
        ...
