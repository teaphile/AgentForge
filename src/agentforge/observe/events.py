"""Async pub/sub event bus for real-time event streaming."""

from __future__ import annotations

from typing import Callable, Coroutine

from agentforge.observe.tracer import TraceEvent


class EventBus:

    def __init__(self):
        self._subscribers: list[Callable[[TraceEvent], Coroutine]] = []
        self._sync_subscribers: list[Callable[[TraceEvent], None]] = []

    def subscribe(self, callback: Callable[[TraceEvent], Coroutine]):
        self._subscribers.append(callback)

    def subscribe_sync(self, callback: Callable[[TraceEvent], None]):
        self._sync_subscribers.append(callback)

    async def emit(self, event: TraceEvent):
        for sync_cb in self._sync_subscribers:
            try:
                sync_cb(event)
            except Exception:
                pass  # Don't let subscriber errors break execution

        for async_cb in self._subscribers:
            try:
                await async_cb(event)
            except Exception:
                pass

    def clear(self):
        self._subscribers.clear()
        self._sync_subscribers.clear()
