"""Run inside the runner container, as its own user and outside the sandbox's seccomp filter:
proves the container itself has no network (SE document NFR-S7, #25).

    docker compose exec -T runner python - < runner/tests/network_check.py

Coolify adds its own network to every service it deploys, so an "internal" network wasn't enough;
with network_mode none there is only the loopback interface, and nothing to reach.
"""

import json
import os
import socket
import sys

interfaces = sorted(os.listdir("/sys/class/net"))
reached = {}
for name, host, port in [
    ("internet", "1.1.1.1", 443),
    ("internet dns", "8.8.8.8", 53),
    ("api", "api", 8000),
    ("db", "db", 5432),
    ("web", "web", 80),
    ("host", "host.docker.internal", 22),
    ("docker bridge", "172.17.0.1", 22),
]:
    try:
        socket.create_connection((host, port), timeout=3).close()
        reached[name] = "REACHED"
    except OSError as e:
        reached[name] = type(e).__name__
try:
    socket.getaddrinfo("example.com", 443)
    reached["dns lookup"] = "REACHED"
except OSError as e:
    reached["dns lookup"] = type(e).__name__

print(json.dumps({"interfaces": interfaces, "reached": reached}))
ok = interfaces == ["lo"] and "REACHED" not in reached.values()
print(
    "PASS  the runner container has no network"
    if ok
    else "FAIL  the runner container can reach the network"
)
sys.exit(0 if ok else 1)
