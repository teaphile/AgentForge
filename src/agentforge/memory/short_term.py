"""Ephemeral in-process memory for a single workflow run."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from agentforge.memory.base import BaseMemory


class ShortTermMemory(BaseMemory):

    def __init__(self, max_items: int = 100, shared: bool = True):
        self.max_items = max_items
        self.shared = shared
        self._store: list[dict] = []

    async def store(self, agent_name: str, content: str, importance: float = 0.5, metadata: dict | None = None) -> str:
        memory_id = str(uuid.uuid4())
        item = {
            "id": memory_id,
            "agent_name": agent_name,
            "content": content,
            "importance": importance,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        self._store.append(item)

        # Sliding window — remove oldest if over limit
        if len(self._store) > self.max_items:
            self._store = self._store[-self.max_items :]

        return memory_id

    async def recall(self, agent_name: str, query: str, limit: int = 5) -> list[dict]:
        """Keyword-based recall with importance weighting."""
        query_words = set(query.lower().split())
        candidates = self._store if self.shared else [m for m in self._store if m["agent_name"] == agent_name]

        scored: list[tuple[float, dict]] = []
        for mem in candidates:
            content_lower = mem["content"].lower()
            # Score: fraction of query words found + importance bonus
            matches = sum(1 for w in query_words if w in content_lower)
            score = (matches / max(len(query_words), 1)) + mem["importance"] * 0.3
            scored.append((score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"content": m["content"], "importance": m["importance"], "created_at": m["created_at"]}
            for _, m in scored[:limit]
        ]

    async def clear(self, agent_name: str | None = None):
        if agent_name is None:
            self._store.clear()
        else:
            self._store = [m for m in self._store if m["agent_name"] != agent_name]
