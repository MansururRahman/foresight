"""In-process sliding-window rate limiter. Per-instance only; fine for a single API replica."""

import ipaddress
import time
from collections import deque
from collections.abc import Callable


def rate_limit_key(host: str) -> str:
    """Bucket key for a client address: IPv6 clients share their /64, since one host can own it."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return str(ip.ipv4_mapped)
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return host


class RateLimiter:
    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 10_000,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def __len__(self) -> int:
        return len(self._hits)

    def hit(self, key: str) -> bool:
        """Record a request for `key`. Returns False when the key is over its limit."""
        now = self._clock()
        cutoff = now - self.window_seconds
        if len(self._hits) >= self.max_keys:
            self._forget_expired(cutoff)
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()

    def _forget_expired(self, cutoff: float) -> None:
        # Keys whose newest hit left the window hold no state worth keeping; without this the
        # dict grows by one entry per distinct client for the life of the process.
        stale = [k for k, hits in self._hits.items() if not hits or hits[-1] <= cutoff]
        for k in stale:
            del self._hits[k]
