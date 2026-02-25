"""Tests for short-term memory."""

from __future__ import annotations

import pytest

from agentforge.memory.short_term import ShortTermMemory


class TestShortTermMemory:
    @pytest.mark.asyncio
    async def test_store_and_recall(self):
        mem = ShortTermMemory()
        await mem.store("test_agent", "Hello world")
        results = await mem.recall("test_agent", "Hello")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_recall_empty(self):
        mem = ShortTermMemory()
        results = await mem.recall("agent", "nothing")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_clear(self):
        mem = ShortTermMemory()
        await mem.store("agent", "data")
        await mem.clear("agent")
        results = await mem.recall("agent", "data")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_sliding_window(self):
        mem = ShortTermMemory(max_items=3)
        for i in range(5):
            await mem.store("agent", f"message_{i}")
        assert len(mem._store) <= 3

    @pytest.mark.asyncio
    async def test_keyword_matching(self):
        mem = ShortTermMemory()
        await mem.store("agent", "Python is a great programming language")
        await mem.store("agent", "JavaScript is used for web development")
        results = await mem.recall("agent", "Python programming")
        assert any("Python" in r.get("content", "") for r in results)
