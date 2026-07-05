"""Polite rate limiting: never fire two requests at the same host faster than a minimum
interval apart. Per-host state, one lock per host so concurrent fetches to *different* hosts
never block each other."""

from __future__ import annotations

import asyncio
import time


class PoliteRateLimiter:
    """Enforces a minimum delay between requests to the same host."""

    def __init__(self, *, min_interval_seconds: float = 2.0) -> None:
        if min_interval_seconds < 0:
            raise ValueError("min_interval_seconds must be >= 0")
        self._min_interval_seconds = min_interval_seconds
        self._last_request_at: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def wait(self, host: str) -> None:
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            last = self._last_request_at.get(host)
            if last is not None:
                remaining = self._min_interval_seconds - (time.monotonic() - last)
                if remaining > 0:
                    await asyncio.sleep(remaining)
            self._last_request_at[host] = time.monotonic()
