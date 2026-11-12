"""Per-client rate limits for login, registration and answer submission (NFR-S6).

Counts live in memory, which is right for the single API process we run. With several processes
or replicas each would count separately, and this would need a shared store.
"""

import math
import time
from collections import defaultdict, deque
from collections.abc import Callable
from functools import cache
from ipaddress import ip_address, ip_network

from fastapi import HTTPException, Request, status

# Cloudflare's edge servers, from https://www.cloudflare.com/ips/ (checked 2026-11-02).
CLOUDFLARE_NETWORKS = [
    ip_network(n)
    for n in (
        "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
        "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
        "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
        "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
        "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32",
        "2405:8100::/32", "2a06:98c0::/29", "2c0f:f248::/32",
    )
]  # fmt: skip


@cache
def is_cloudflare(host: str) -> bool:
    try:
        address = ip_address(host)
    except ValueError:
        return False
    return any(address in network for network in CLOUDFLARE_NETWORKS)


def client_ip(request: Request) -> str:
    """The student's address, as far as we can trust it.

    `request.client` is the address that connected to the server's proxy: uvicorn only trusts the
    private networks of our own containers (api/Dockerfile), so a client can't fake it. Behind
    Cloudflare that address is a Cloudflare edge, shared by many students, and the student's own
    address is in CF-Connecting-IP. That header is believed only when the request really came
    from Cloudflare; anyone connecting to the server directly could set it to anything.
    """
    peer = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("cf-connecting-ip")
    if forwarded and is_cloudflare(peer):
        return forwarded.strip()
    return peer


class RateLimiter:
    """Allows `limit` requests per key in any `window` seconds (a sliding window)."""

    def __init__(
        self,
        limit: int,
        window: float,
        clock: Callable[[], float] = time.monotonic,
        message: str = "Too many attempts. Wait a minute and try again.",
    ) -> None:
        self.limit = limit
        self.window = window
        self.clock = clock
        self.message = message
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

    def check(self, key: str) -> None:
        """Records a request, or refuses it with 429 and Retry-After."""
        wait = self.hit(key)
        if wait is not None:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=self.message,
                headers={"Retry-After": str(math.ceil(wait))},
            )

    def reset(self) -> None:
        self._hits.clear()


# Guessing one account's password: 10 tries a minute from one address.
login_account_limiter = RateLimiter(limit=10, window=60)
# Spraying many accounts from one address. Generous, because a whole campus or residence can share
# one public address, and a class may log in at the same moment.
login_address_limiter = RateLimiter(limit=60, window=60)
register_limiter = RateLimiter(limit=20, window=600)
