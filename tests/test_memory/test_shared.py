"""Tests for shared memory and factory."""

from __future__ import annotations

import pytest

from agentforge.memory.shared import SharedMemory, create_memory
from agentforge.memory.short_term import ShortTermMemory


class TestSharedMemory:
    @pytest.mark.asyncio
    async def test_shared_store_and_recall(self):
        backend = ShortTermMemory()
        shared = SharedMemory(backend=backend)
        await shared.store("team", "Shared knowledge")
        results = await shared.recall("team", "knowledge")
        assert len(results) >= 1


class TestCreateMemory:
    def test_create_short_term(self):
        config = {
            "enabled": True,
            "backend": "short_term",
        }
        mem = create_memory(config)
        assert mem is not None

    def test_create_sqlite(self, tmp_path):
        config = {
            "enabled": True,
            "backend": "sqlite",
            "path": str(tmp_path / "test.db"),
        }
        mem = create_memory(config)
        assert mem is not None

    def test_create_disabled(self):
        config = {"enabled": False}
        mem = create_memory(config)
        assert mem is None
