"""In-process sliding-window rate limiter. Per-instance only; fine for a single API replica."""

import time
from collections import deque
from collections.abc import Callable


class RateLimiter:
    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str) -> bool:
        """Record a request for `key`. Returns False when the key is over its limit."""
        now = self._clock()
        cutoff = now - self.window_seconds
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()
