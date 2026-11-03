"""Hostile code against the real runner container, with docker-compose.yml's limits (NFR-S7).

CI starts the runner on its internal network and runs this, standard library only, from a second
container on that network:

    python container_check.py http://runner:8000

It checks what only the container can enforce (no network, a read-only filesystem, Docker's
memory and process limits) and that the runner is still healthy after every attack.
"""

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://runner:8000"
failures: list[str] = []


def run(code: str, tests: list[dict[str, Any]] | None = None) -> tuple[int, dict[str, Any]]:
    body = json.dumps({"code": code, "tests": tests or []}).encode()
    req = urllib.request.Request(
        f"{BASE}/run", data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def check(ok: bool, name: str, detail: object = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)
    if not ok:
        failures.append(name)


def healthy() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE}/health", timeout=10) as res:
            return bool(res.status == 200)
    except OSError:
        return False


def wait_until_healthy(seconds: float = 60) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if healthy():
            return True
        time.sleep(1)
    return False


def stdout_of(code: str) -> str:
    _, body = run(code)
    return str(body.get("stdout", ""))


check(wait_until_healthy(), "the runner is up")

status, body = run(
    "def add(a, b):\n    return a + b",
    [{"name": "adds", "kind": "call", "call": "add(2, 3)", "expected": 5}],
)
check(
    status == 200 and body["outcome"] == "completed" and body["tests"][0]["passed"],
    "ordinary code runs and is graded",
    body.get("outcome"),
)

network = """
import socket
results = []
for host, port in [("1.1.1.1", 443), ("8.8.8.8", 53), ("api", 8000), ("db", 5432)]:
    try:
        socket.create_connection((host, port), timeout=3).close()
        results.append(f"{host} open")
    except OSError:
        results.append(f"{host} blocked")
try:
    socket.getaddrinfo("example.com", 443)
    results.append("dns works")
except OSError:
    results.append("dns blocked")
print(", ".join(results))
"""
out = stdout_of(network)
check(
    "open" not in out and "dns works" not in out,
    "no internet, no DNS, no API or database",
    out.strip(),
)

files = """
import os
attempts = {}
for path in ["/app/runner/harness.py", "/app/new.py", "/etc/passwd", "/home/x", "/var/tmp/x"]:
    try:
        open(path, "a").close()
        attempts[path] = "written"
    except OSError:
        attempts[path] = "refused"
print(attempts)
"""
out = stdout_of(files)
check("written" not in out, "nothing outside its own folder can be written", out.strip())

out = stdout_of("import os\nprint(sorted(os.environ))")
check(
    out.strip() == "['HOME', 'LANG', 'PATH', 'RESULT_FD', 'RUNNER_PID']",
    "the environment holds no secrets",
    out.strip(),
)

out = stdout_of(
    "import os\ntry:\n    print(open('/proc/1/environ').read()[:50])\nexcept OSError:\n    print('refused')"
)
check(out.strip() == "refused", "the runner process's environment can't be read", out.strip())

out = stdout_of(
    "import os\nprint(os.getuid(), open('/proc/self/status').read().split('CapEff:')[1].split()[0])"
)
check(
    out.split() == ["10002", "0000000000000000"], "unprivileged user, no capabilities", out.strip()
)

out = stdout_of(
    "import os, signal\nfor target in [os.getppid(), 1, -1]:\n    try:\n"
    "        os.kill(target, signal.SIGKILL)\n        print('killed', target)\n"
    "    except OSError:\n        print('refused', target)"
)
check("killed" not in out, "student code can't kill the runner or anything else", out.split())
check(healthy(), "the runner is healthy after the kill attempts")

bomb = "import os\nwhile True:\n    try:\n        os.fork()\n    except OSError:\n        pass"
status, body = run(bomb)
check(
    status == 200 and body["outcome"] == "timeout",
    "a fork bomb starts nothing and times out",
    body.get("outcome"),
)
check(healthy(), "the runner is healthy after the fork bomb")

status, body = run("x = bytearray(1024 * 1024 * 1024)")
check(
    body.get("outcome") == "memory_limit",
    "a memory bomb hits the memory limit",
    body.get("outcome"),
)

status, body = run("while True:\n    print('x' * 10000)")
check(
    body.get("outcome") == "output_limit" and len(str(body.get("stdout"))) == 1024 * 1024,
    "huge output is cut at 1 MB",
    body.get("outcome"),
)

started = time.monotonic()
status, body = run("while True:\n    pass")
took = time.monotonic() - started
check(
    body.get("outcome") == "timeout" and took < 15,
    "an infinite loop stops within the limits",
    f"{body.get('outcome')} in {took:.1f} s",
)

out = stdout_of("import os\nprint(os.access('/tmp', os.W_OK), os.access('/', os.W_OK))")
check(out.split() == ["True", "False"], "only /tmp is writable", out.strip())

# The container's own limits, as a run sees them (cgroup v2): these are what keep the rest of the
# server safe whatever the code does.
limits = stdout_of(
    "import os\nfor name in ['memory.max', 'memory.swap.max', 'cpu.max', 'cpu.weight', 'pids.max']:\n"
    "    try:\n        print(name, open('/sys/fs/cgroup/' + name).read().strip())\n"
    "    except OSError:\n        print(name, '?')\nprint('oom_score_adj', open('/proc/self/oom_score_adj').read().strip())"
)
seen = dict(line.split(" ", 1) for line in limits.splitlines() if " " in line)
check(
    seen.get("memory.max") == str(768 * 1024 * 1024),
    "memory capped at 768 MB",
    seen.get("memory.max"),
)
check(seen.get("memory.swap.max") == "0", "no swap", seen.get("memory.swap.max"))
check(seen.get("cpu.max") == "200000 100000", "CPU capped at 2", seen.get("cpu.max"))
check(
    seen.get("cpu.weight", "100").isdigit() and int(seen.get("cpu.weight", "100")) < 100,
    "lower CPU weight than the rest of the app",
    seen.get("cpu.weight"),
)
check(seen.get("pids.max") == "64", "at most 64 processes", seen.get("pids.max"))
check(
    seen.get("oom_score_adj") == "1000",
    "killed first if the server runs out of memory",
    seen.get("oom_score_adj"),
)

out = stdout_of(
    "import os\nresults = []\nfor how in ['w', 'a', 'x']:\n    try:\n        open('/tmp/fill', how)\n"
    "        results.append('written')\n    except OSError:\n        results.append('refused')\nprint(results)"
)
check("written" not in out, "not even /tmp can be written to (it can't be filled up)", out.strip())

spy_code = (
    "import os, time\ntime.sleep(1)\nseen = []\nfor pid in os.listdir('/proc'):\n"
    "    if pid.isdigit() and int(pid) != os.getpid():\n"
    "        for part in ['environ', 'mem', 'maps']:\n"
    "            try:\n                open(f'/proc/{pid}/{part}', 'rb').read(1)\n                seen.append(part)\n"
    "            except OSError:\n                pass\n"
    "        try:\n            os.readlink(f'/proc/{pid}/cwd')\n            seen.append('cwd')\n"
    "        except OSError:\n            pass\n"
    "others = [r for r in os.listdir('..') if r != os.path.basename(os.getcwd())]\n"
    "files = [f for r in others for f in os.listdir(os.path.join('..', r))]\n"
    "print('readable', seen, 'files', files)"
)
victim_result: list[str] = []
victim = threading.Thread(
    target=lambda: victim_result.append(stdout_of("import time\nprint('private')\ntime.sleep(3)"))
)
victim.start()
spied = stdout_of(spy_code)
victim.join()
check(
    spied.strip() == "readable [] files []",
    "one run can't see into another running at the same time",
    spied.strip(),
)

_, body = run("import sys\nprint('a' + chr(0) + 'b')\nraise ValueError('x' + chr(0))")
check(
    chr(0) not in json.dumps(body, ensure_ascii=False),
    "no NUL goes back to the API",
    body.get("outcome"),
)

results: list[int] = []


def slow() -> None:
    results.append(run("import time\ntime.sleep(4)")[0])


threads = [threading.Thread(target=slow) for _ in range(8)]
for t in threads:
    t.start()
for t in threads:
    t.join()
check(
    results.count(200) == 4 and results.count(503) == 4,
    "at most four runs at once; the rest are told it's busy",
    sorted(results),
)

check(healthy(), "the runner is still healthy at the end")
print(f"\n{len(failures)} failed" if failures else "\nall passed")
sys.exit(1 if failures else 0)
