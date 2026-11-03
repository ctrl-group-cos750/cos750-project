"""Talks to the code runner (runner/README.md). The runner has no network: it listens on a Unix
socket on a volume only it and the API mount, so this is the only way to reach it."""

import http.client
import json
import os
import socket
from typing import Any

RUNNER_SOCKET = os.environ.get("RUNNER_SOCKET", "/run/runner/runner.sock")
TIMEOUT = 15.0  # a run takes at most 10 s of wall time; the rest is queueing and start-up
UNAVAILABLE = "Code can't be run right now. Try again in a moment."


class RunnerUnavailable(Exception):  # read as "the runner is unavailable"
    """The runner is busy, down or too slow. `str(e)` is a message for the student."""


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, path: str, timeout: float) -> None:
        super().__init__("runner", timeout=timeout)
        self.socket_path = path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect(self.socket_path)
        except OSError:
            sock.close()
            raise
        self.sock = sock


def run_code(
    code: str, tests: list[dict[str, Any]], *, path: str | None = None, timeout: float = TIMEOUT
) -> dict[str, Any]:
    """Runs the student's code against the tests and returns the runner's result (camelCase).

    Raises RunnerUnavailable, with a message to show the student, when the runner is busy (its own
    "busy" message), not running, or doesn't answer in time.
    """
    conn = _UnixConnection(path or RUNNER_SOCKET, timeout)
    try:
        conn.request(
            "POST",
            "/run",
            body=json.dumps({"code": code, "tests": tests}),
            headers={"Content-Type": "application/json"},
        )
        res = conn.getresponse()
        body = json.loads(res.read() or b"null")
    except (OSError, ValueError) as e:  # no socket, refused, timed out, not JSON
        raise RunnerUnavailable(UNAVAILABLE) from e
    finally:
        conn.close()
    if res.status == 503 and isinstance(body, dict) and isinstance(body.get("detail"), str):
        raise RunnerUnavailable(body["detail"])
    if res.status != 200 or not isinstance(body, dict):
        raise RunnerUnavailable(UNAVAILABLE)
    return body
