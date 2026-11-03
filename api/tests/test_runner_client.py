import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingUnixStreamServer

import pytest

from app.runner_client import UNAVAILABLE, RunnerUnavailable, run_code


class FakeRunner(BaseHTTPRequestHandler):
    """Answers like the runner, over a Unix socket. `reply` sets the status and body."""

    reply: tuple[int, object] = (200, {})
    seen: list[dict[str, object]] = []  # noqa: RUF012

    def address_string(self) -> str:  # a Unix socket has no client address
        return "runner-test"

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        FakeRunner.seen.append(
            {
                "path": self.path,
                "type": self.headers["Content-Type"],
                "body": json.loads(self.rfile.read(length)),
            }
        )
        status, body = FakeRunner.reply
        payload = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_: object) -> None:
        pass


@pytest.fixture
def runner(tmp_path: Path) -> Iterator[str]:
    path = str(tmp_path / "runner.sock")
    server = ThreadingUnixStreamServer(path, FakeRunner)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    FakeRunner.seen = []
    yield path
    server.shutdown()
    server.server_close()


def test_a_run_goes_to_the_runner_and_its_result_comes_back(runner: str) -> None:
    result = {"outcome": "completed", "tests": [{"name": "t", "passed": True, "message": None}]}
    FakeRunner.reply = (200, result)
    tests = [{"name": "t", "kind": "call", "call": "f()", "expected": 1}]
    assert run_code("def f():\n    return 1", tests, path=runner) == result
    assert FakeRunner.seen == [
        {
            "path": "/run",
            "type": "application/json",
            "body": {"code": "def f():\n    return 1", "tests": tests},
        }
    ]


def test_the_runners_busy_message_is_passed_on(runner: str) -> None:
    FakeRunner.reply = (503, {"detail": "The code runner is busy. Try again in a moment."})
    with pytest.raises(RunnerUnavailable, match="The code runner is busy"):
        run_code("", [], path=runner)


@pytest.mark.parametrize(
    "reply",
    [
        (500, {"detail": "boom"}),
        (200, b"not json"),
        (200, [1, 2]),
        (422, {"detail": [{"msg": "x"}]}),
    ],
    ids=["server error", "not json", "not an object", "validation error"],
)
def test_anything_else_unexpected_is_unavailable(runner: str, reply: tuple[int, object]) -> None:
    FakeRunner.reply = reply
    with pytest.raises(RunnerUnavailable, match=UNAVAILABLE):
        run_code("", [], path=runner)


def test_a_runner_that_is_not_running_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(RunnerUnavailable, match=UNAVAILABLE):
        run_code("", [], path=str(tmp_path / "no-such.sock"))


def test_a_runner_that_does_not_answer_in_time_is_unavailable(tmp_path: Path) -> None:
    import socket

    path = str(tmp_path / "silent.sock")
    silent = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    silent.bind(path)
    silent.listen()  # accepts the connection but never answers
    try:
        with pytest.raises(RunnerUnavailable, match=UNAVAILABLE):
            run_code("", [], path=path, timeout=0.3)
    finally:
        silent.close()
