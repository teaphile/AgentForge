"""Retry with exponential backoff."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine


class RetryHandler:

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max(0, max_retries)
        self.base_delay = base_delay

    async def execute_with_retry(
        self,
        func: Callable[..., Coroutine],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = self.base_delay * (2**attempt)
                    await asyncio.sleep(delay)

        raise last_error  # type: ignore[misc]
