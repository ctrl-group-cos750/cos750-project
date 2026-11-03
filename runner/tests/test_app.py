import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import runner.app
from runner.app import app, protect_this_process


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_a_run_returns_camel_case_results(client: TestClient) -> None:
    res = client.post(
        "/run",
        json={
            "code": "def double(x):\n    return 2 * x\nprint('hi')",
            "tests": [{"name": "doubles", "kind": "call", "call": "double(21)", "expected": 42}],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["outcome"] == "completed"
    assert body["tests"] == [{"name": "doubles", "passed": True, "message": None}]
    assert body["stdout"] == "hi\n"
    assert isinstance(body["durationMs"], int)


@pytest.mark.parametrize(
    "test",
    [
        {"name": "no call", "kind": "call"},
        {"name": "no code", "kind": "code"},
        {"name": "", "kind": "code", "code": "pass"},
        {"name": "odd kind", "kind": "shell", "code": "ls"},
        {"name": "extra", "kind": "code", "code": "pass", "sudo": True},
    ],
)
def test_malformed_tests_are_refused(client: TestClient, test: dict[str, object]) -> None:
    assert client.post("/run", json={"code": "", "tests": [test]}).status_code == 422


def test_too_much_code_is_refused(client: TestClient) -> None:
    assert client.post("/run", json={"code": "x" * 100_001, "tests": []}).status_code == 422


def test_too_many_tests_are_refused(client: TestClient) -> None:
    tests = [{"name": f"t{i}", "kind": "code", "code": "pass"} for i in range(51)]
    assert client.post("/run", json={"code": "", "tests": tests}).status_code == 422


def test_when_every_slot_is_taken_the_answer_is_busy(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner.app, "_slots", asyncio.Semaphore(0))
    monkeypatch.setattr(runner.app, "BUSY_WAIT", 0.05)
    res = client.post("/run", json={"code": "", "tests": []})
    assert res.status_code == 503
    assert res.json() == {"detail": "The code runner is busy. Try again in a moment."}
    assert res.headers["retry-after"] == "2"


def test_slots_are_given_back(client: TestClient) -> None:
    for _ in range(runner.app.MAX_RUNS + 2):
        assert client.post("/run", json={"code": "", "tests": []}).status_code == 200


def test_no_docs_or_schema_are_served(client: TestClient) -> None:
    for path in ["/docs", "/redoc", "/openapi.json"]:
        assert client.get(path).status_code == 404


def test_the_runner_process_cannot_be_read_by_the_code_it_runs(client: TestClient) -> None:
    # /proc/<runner>/environ and its memory are closed to same-user processes once non-dumpable.
    assert protect_this_process()
    res = client.post(
        "/run",
        json={
            "code": "import os\ntry:\n    open(f'/proc/{os.getppid()}/environ').read()\n"
            "    print('read it')\nexcept OSError:\n    print('refused')",
            "tests": [],
        },
    )
    assert res.json()["stdout"] == "refused\n"
