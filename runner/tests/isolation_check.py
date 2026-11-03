"""Proves that whatever happens in the sandbox, only running code is affected.

CI starts the whole stack (web, api, db, runner) and runs this, standard library only, from a
container on both networks:

    python isolation_check.py flood http://web http://runner:8000
    python isolation_check.py runner-down http://web

"flood" measures the app at rest, then keeps the sandbox saturated with hostile code (infinite
loops, fork bombs, memory bombs, output floods, more requests than it takes) while measuring again:
the app must answer every request, and stay fast. "runner-down" runs after CI stops the runner:
the app must still work.
"""

import json
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request

failures: list[str] = []


def check(ok: bool, name: str, detail: object = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)
    if not ok:
        failures.append(name)


def request(
    url: str, body: object = None, cookie: str | None = None, timeout: float = 30
) -> tuple[int, dict[str, str], float]:
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"} if data else {}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            res.read()
            return res.status, dict(res.headers), time.perf_counter() - start
    except urllib.error.HTTPError as e:
        e.read()
        return e.code, dict(e.headers), time.perf_counter() - start
    except OSError:
        return 0, {}, time.perf_counter() - start


def timed(url: str, body: object = None, cookie: str | None = None) -> tuple[int, float]:
    status, _, seconds = request(url, body, cookie)
    return status, seconds


class App:
    """A student using the app: the page, the API health, their account, logging in."""

    def __init__(self, web: str) -> None:
        self.web = web.rstrip("/")
        self.email = f"isolation-{int(time.time() * 1000)}@example.com"
        self.password = "Isolation run 1!"
        status, headers, _ = request(
            f"{self.web}/api/auth/register",
            {"email": self.email, "password": self.password, "displayName": "Checker"},
        )
        if status != 201:
            sys.exit(f"setup: register returned {status}")
        self.cookie = headers["set-cookie"].split(";")[0]

    def sample(self, rounds: int) -> dict[str, list[tuple[int, float]]]:
        timings: dict[str, list[tuple[int, float]]] = {
            "page": [],
            "health": [],
            "me": [],
            "login": [],
        }
        for i in range(rounds):
            timings["page"].append(timed(f"{self.web}/"))
            timings["health"].append(timed(f"{self.web}/api/health"))
            timings["me"].append(timed(f"{self.web}/api/auth/me", cookie=self.cookie))
            if i % 4 == 0:  # logins hash a password: a few are enough
                credentials = {"email": self.email, "password": self.password}
                timings["login"].append(timed(f"{self.web}/api/auth/login", credentials))
        return timings


def summarise(label: str, timings: dict[str, list[tuple[int, float]]]) -> dict[str, float]:
    medians = {}
    for name, samples in timings.items():
        ok = sum(200 <= s < 300 for s, _ in samples)
        median = statistics.median(t for _, t in samples)
        medians[name] = median
        print(
            f"  {label:8s} {name:6s} {ok}/{len(samples)} ok, median {median * 1000:6.1f} ms, "
            f"max {max(t for _, t in samples) * 1000:6.1f} ms"
        )
    return medians


HOSTILE = [
    "while True:\n    pass",
    "import os\nwhile True:\n    try:\n        os.fork()\n    except OSError:\n        pass",
    "x = []\nwhile True:\n    x.append(bytearray(10 ** 6))",
    "while True:\n    print('x' * 10000)",
    "import time\ntime.sleep(60)",
    "import os, signal\nfor t in [os.getppid(), 1, -1]:\n    try:\n        os.kill(t, signal.SIGKILL)\n"
    "    except OSError:\n        pass\nwhile True:\n    pass",
]


def flood(runner: str, stop: threading.Event, outcomes: list[int]) -> None:
    i = 0
    while not stop.is_set():
        body = {"code": HOSTILE[i % len(HOSTILE)], "tests": []}
        status, _, _ = request(f"{runner}/run", body, timeout=60)
        outcomes.append(status)
        i += 1


def flood_check(web: str, runner: str) -> None:
    app = App(web)
    calm = summarise("at rest", app.sample(12))

    stop, outcomes = threading.Event(), list[int]()
    attackers = [threading.Thread(target=flood, args=(runner, stop, outcomes)) for _ in range(12)]
    for t in attackers:
        t.start()
    time.sleep(5)  # let the sandbox fill up
    busy = app.sample(24)
    stop.set()
    for t in attackers:
        t.join()
    loaded = summarise("flooded", busy)

    print(
        f"  sandbox requests during the flood: {len(outcomes)}, "
        f"answered {outcomes.count(200)}, busy {outcomes.count(503)}, other {len(outcomes) - outcomes.count(200) - outcomes.count(503)}"
    )
    check(
        outcomes.count(200) > 0 and outcomes.count(503) > 0,
        "the sandbox was saturated (runs and 'busy' answers)",
    )
    for name, samples in busy.items():
        check(
            all(200 <= s < 300 for s, _ in samples),
            f"every {name} request succeeded during the flood",
        )
        allowed = max(calm[name] * 3, calm[name] + 0.25)
        check(
            loaded[name] <= allowed,
            f"{name} stayed fast (median under {allowed * 1000:.0f} ms)",
            f"{calm[name] * 1000:.1f} -> {loaded[name] * 1000:.1f} ms",
        )
    status, _, _ = request(f"{runner}/health")
    check(status == 200, "the runner itself is healthy afterwards")


def runner_down_check(web: str) -> None:
    app = App(web)
    timings = app.sample(4)
    summarise("no runner", timings)
    for name, samples in timings.items():
        check(all(200 <= s < 300 for s, _ in samples), f"{name} works with the runner stopped")


def main() -> None:
    mode = sys.argv[1]
    if mode == "flood":
        flood_check(sys.argv[2], sys.argv[3].rstrip("/"))
    else:
        runner_down_check(sys.argv[2])
    print(f"\n{len(failures)} failed" if failures else "\nall passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
