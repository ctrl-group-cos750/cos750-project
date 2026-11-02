#!/usr/bin/env python3
"""Stress test for a deployed Ctrl Academy. Standard library only.

    STAGING_PASSWORD=... python3 scripts/load-test.py ramp       # 1 to 240 users, 15 s per step
    STAGING_PASSWORD=... python3 scripts/load-test.py burst 1000 # requests released at one instant
    STAGING_PASSWORD=... python3 scripts/load-test.py sustained  # 40 users for 2 minutes
    STAGING_PASSWORD=... python3 scripts/load-test.py login 50   # logins at one instant (hashing)

Each simulated user keeps one HTTPS connection open and sends requests back to back to
/api/auth/me (signed in), /api/health and /. Latency is per request, in ms; "> 0.5 s" is the share
of requests answered more than half a second after they were sent. The ramp stops early when more
than 5% of requests fail or the slowest 5% take over 5 s.

Staging shares its server with other apps: run it when nobody is testing or presenting, and never
during the pilot or the demo. SE document §14, "Load testing".
"""

import argparse
import hashlib
import http.client
import json
import os
import sys
import threading
import time
from collections.abc import Callable
from urllib.parse import urlsplit

UA = "ctrl-academy-load-test"
PASSWORD = "Stress run pw 1!"  # follows the password rules; the display name is "Tester"
MIX = [("GET", "/api/auth/me"), ("GET", "/api/health"), ("GET", "/")]


class Client:
    """One simulated user: one keep-alive connection."""

    def __init__(self, base: str, gate: str | None) -> None:
        parts = urlsplit(base)
        self.host, self.tls, self.gate = parts.netloc, parts.scheme == "https", gate
        self.conn: http.client.HTTPConnection | None = None

    def request(
        self, method: str, path: str, body: object = None, cookie: str | None = None
    ) -> tuple[int, float, str | None]:
        headers = {"User-Agent": UA, "Connection": "keep-alive"}
        cookies = [c for c in (self.gate, cookie) if c]
        if cookies:
            headers["Cookie"] = "; ".join(cookies)
        data = None if body is None else json.dumps(body).encode()
        if data is not None:
            headers["Content-Type"] = "application/json"
        for attempt in (1, 2):  # a keep-alive connection may have been closed by the server
            try:
                if self.conn is None:
                    kind = http.client.HTTPSConnection if self.tls else http.client.HTTPConnection
                    self.conn = kind(self.host, timeout=30)
                start = time.perf_counter()
                self.conn.request(method, path, body=data, headers=headers)
                res = self.conn.getresponse()
                res.read()
                return res.status, time.perf_counter() - start, res.getheader("set-cookie")
            except Exception:
                self.conn = None
                if attempt == 2:
                    return 0, 30.0, None
        raise AssertionError("unreachable")


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(p / 100 * len(ordered)))] if ordered else 0.0


def report(label: str, results: list[tuple[int, float]], seconds: float) -> dict[str, float]:
    latencies = [d for _, d in results]
    failed: dict[int, int] = {}
    for status, _ in results:
        if not (200 <= status < 400 or status == 401):
            failed[status] = failed.get(status, 0) + 1
    n = len(results)
    behind = sum(d > 0.5 for d in latencies) / n
    error_rate = sum(failed.values()) / n
    print(
        f"{label:22s} {n:6d} req {n / seconds:7.1f} req/s"
        f"  p50 {percentile(latencies, 50) * 1000:6.0f}  p95 {percentile(latencies, 95) * 1000:6.0f}"
        f"  p99 {percentile(latencies, 99) * 1000:6.0f}  max {max(latencies) * 1000:6.0f}"
        f"  >0.5s {behind * 100:5.1f}%  failed {failed or 0}",
        flush=True,
    )
    return {"p95": percentile(latencies, 95), "errors": error_rate}


Results = list[tuple[int, float]]


def run(
    new_client: Callable[[], Client], users: int, seconds: float, cookie: str
) -> tuple[Results, float]:
    results: Results = []
    lock = threading.Lock()
    stop = time.monotonic() + seconds

    def user(i: int) -> None:
        client, n = new_client(), i
        while time.monotonic() < stop:
            method, path = MIX[n % len(MIX)]
            n += 1
            status, took, _ = client.request(method, path, cookie=cookie)
            with lock:
                results.append((status, took))

    threads = [threading.Thread(target=user, args=(i,)) for i in range(users)]
    start = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results, time.monotonic() - start


def at_once(
    clients: list[Client], send: Callable[[int, Client], tuple[int, float]]
) -> tuple[Results, float]:
    """Opens every connection first, then releases all requests at the same instant."""
    for c in clients:
        c.request("GET", "/api/health")
    barrier, lock = threading.Barrier(len(clients)), threading.Lock()
    results: Results = []

    def fire(i: int, c: Client) -> None:
        barrier.wait()
        status, took = send(i, c)
        with lock:
            results.append((status, took))

    threads = [threading.Thread(target=fire, args=(i, c)) for i, c in enumerate(clients)]
    start = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results, time.monotonic() - start


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("mode", choices=["ramp", "burst", "sustained", "login"])
    parser.add_argument("size", nargs="?", type=int, help="burst or login: how many at once")
    parser.add_argument("--base", default="https://staging.ctrlacademy.co.za")
    parser.add_argument(
        "--steps", default="1,5,10,20,40,80,120,160,240", help="ramp: users per step"
    )
    parser.add_argument("--seconds", type=int, default=120, help="sustained: how long")
    parser.add_argument("--users", type=int, default=40, help="sustained: how many users")
    parser.add_argument(
        "--api-only", action="store_true", help="skip / (for a bare local API without nginx)"
    )
    args = parser.parse_args()
    if args.api_only:
        MIX[:] = [m for m in MIX if m[1].startswith("/api/")]

    password = os.environ.get("STAGING_PASSWORD")
    gate = None
    if password:
        gate = (
            "ctrl_staging="
            + hashlib.sha256(f"ctrl-academy-staging:{password}".encode()).hexdigest()
        )

    def new_client() -> Client:
        return Client(args.base, gate)

    tag = int(time.time())
    setup = new_client()

    def register(email: str) -> str:
        body = {"email": email, "password": PASSWORD, "displayName": "Tester"}
        status, _, cookie = setup.request("POST", "/api/auth/register", body)
        if status != 201 or not cookie:
            sys.exit(f"setup: registering {email} returned {status}")
        return cookie.split(";")[0]

    cookie = register(f"load-{tag}@example.com")

    if args.mode == "ramp":
        print("ramp: each step 15 s; /api/auth/me, /api/health and / in turn; latency in ms")
        for users in [int(s) for s in args.steps.split(",")]:
            results, seconds = run(new_client, users, 15, cookie)
            m = report(f"{users:4d} users", results, seconds)
            if m["errors"] > 0.05 or m["p95"] > 5:
                print("stopping: more than 5% failed, or the slowest 5% took over 5 s")
                break
            time.sleep(3)
    elif args.mode == "burst":
        n = args.size or 300
        results, seconds = at_once(
            [new_client() for _ in range(n)],
            lambda _i, c: c.request("GET", "/api/auth/me", cookie=cookie)[:2],
        )
        report(f"{n} at once", results, seconds)
    elif args.mode == "sustained":
        print(f"sustained: {args.users} users for {args.seconds} s, per 15 s window")
        everything: Results = []
        for w in range(args.seconds // 15):
            results, seconds = run(new_client, args.users, 15, cookie)
            everything += results
            report(f"  {w * 15:4d}-{(w + 1) * 15:4d} s", results, seconds)
        report("  whole run", everything, args.seconds)
    elif args.mode == "login":
        n = args.size or 50
        # Logins are limited to 10 a minute per account and 60 per address: spread over accounts.
        accounts = [f"load-{tag}-{k}@example.com" for k in range((n + 9) // 10)]
        for email in accounts:
            register(email)
        results, seconds = at_once(
            [new_client() for _ in range(n)],
            lambda i, c: c.request(
                "POST",
                "/api/auth/login",
                {"email": accounts[i % len(accounts)], "password": PASSWORD},
            )[:2],
        )
        report(f"{n} logins at once", results, seconds)


if __name__ == "__main__":
    main()
