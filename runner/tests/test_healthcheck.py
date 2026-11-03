import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingUnixStreamServer

import pytest

from runner.healthcheck import healthy


class Health(BaseHTTPRequestHandler):
    status = 200

    def address_string(self) -> str:
        return "healthcheck-test"

    def do_GET(self) -> None:
        self.send_response(Health.status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_: object) -> None:
        pass


@pytest.fixture
def socket_path(tmp_path: Path) -> Iterator[str]:
    path = str(tmp_path / "runner.sock")
    server = ThreadingUnixStreamServer(path, Health)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield path
    server.shutdown()
    server.server_close()


def test_a_runner_that_answers_is_healthy(socket_path: str) -> None:
    Health.status = 200
    assert healthy(socket_path)


def test_a_runner_that_errors_is_not(socket_path: str) -> None:
    Health.status = 500
    assert not healthy(socket_path)


def test_no_runner_is_not_healthy(tmp_path: Path) -> None:
    assert not healthy(str(tmp_path / "missing.sock"))
