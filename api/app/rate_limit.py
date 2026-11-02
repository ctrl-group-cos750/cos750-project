"""Per-client rate limits for login and registration (NFR-S6).

Counts live in memory, which is right for the single API process we run. With several processes
or replicas each would count separately, and this would need a shared store.
"""

import math
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status


class RateLimiter:
    """Allows `limit` requests per client in any `window` seconds (a sliding window)."""

    def __init__(
        self, limit: int, window: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window = window
        self.clock = clock
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str) -> float | None:
        """Records a request. Returns None if allowed, or the seconds to wait if not."""
        now = self.clock()
        hits = self._hits[key]
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return hits[0] + self.window - now
        hits.append(now)
        return None

    def reset(self) -> None:
        self._hits.clear()

    def __call__(self, request: Request) -> None:
        """Use as a route dependency: `dependencies=[Depends(limiter)]`."""
        # Uvicorn runs with --proxy-headers, so this is the student's address, not nginx's.
        client = request.client.host if request.client else "unknown"
        wait = self.hit(client)
        if wait is not None:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Wait a minute and try again.",
                headers={"Retry-After": str(math.ceil(wait))},
            )


login_limiter = RateLimiter(limit=10, window=60)
register_limiter = RateLimiter(limit=5, window=600)
