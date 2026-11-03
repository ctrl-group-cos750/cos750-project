"""Docker's health check: asks the runner for /health over its Unix socket (it has no network)."""

import http.client
import os
import socket
import sys

SOCKET = os.environ.get("RUNNER_SOCKET", "/run/runner/runner.sock")


class UnixConnection(http.client.HTTPConnection):
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


def healthy(path: str = SOCKET) -> bool:
    conn = UnixConnection(path, timeout=5)
    try:
        conn.request("GET", "/health")
        return conn.getresponse().status == 200
    except OSError:
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(0 if healthy() else 1)
