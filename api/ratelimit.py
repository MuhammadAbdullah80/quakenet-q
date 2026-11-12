"""In-memory sliding-window rate limiter, keyed by (bucket, client)."""
from __future__ import annotations

import math
import threading
import time
from collections import deque
from typing import Callable

MAX_KEYS = 10_000


class RateLimiter:
    def __init__(self, limits: dict[str, int], window: float = 60.0, clock: Callable[[], float] = time.monotonic):
        self._limits, self._window, self._clock = dict(limits), window, clock
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, bucket: str, client: str) -> int:
        """Record one request. Returns 0 if allowed, otherwise the seconds to wait."""
        now = self._clock()
        with self._lock:
            if len(self._hits) > MAX_KEYS:      # forget clients whose window has passed
                self._hits = {k: q for k, q in self._hits.items() if q and q[-1] > now - self._window}
            hits = self._hits.setdefault((bucket, client), deque())
            while hits and hits[0] <= now - self._window:
                hits.popleft()
            if len(hits) >= self._limits[bucket]:
                return max(1, math.ceil(hits[0] + self._window - now))
            hits.append(now)
            return 0
