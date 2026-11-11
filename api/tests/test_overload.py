import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

import app.db
import app.main


def test_the_database_pool_has_more_connections_than_requests_run_at_once() -> None:
    pool = app.db.engine.pool
    connections = pool.size() + pool._max_overflow  # type: ignore[attr-defined]
    assert app.main.MAX_IN_FLIGHT < app.db.REQUEST_THREADS < connections


def test_a_request_that_waits_too_long_gets_a_quick_busy_answer(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app.main, "_in_flight", asyncio.Semaphore(0))  # every slot taken
    monkeypatch.setattr(app.main, "QUEUE_WAIT", 0.05)
    res = client.get("/api/auth/me")
    assert res.status_code == 503
    assert res.json() == {"detail": "Ctrl Academy is busy. Try again in a moment."}
    assert res.headers["retry-after"] == "2"
    assert res.headers["cache-control"] == "no-store"


def test_the_health_check_answers_even_when_busy(
    client: TestClient, working_db: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app.main, "_in_flight", asyncio.Semaphore(0))
    monkeypatch.setattr(app.main, "QUEUE_WAIT", 0.05)
    assert client.get("/api/health").status_code == 200


def test_a_slot_is_given_back_after_each_request(client: TestClient, db: Session) -> None:
    for _ in range(app.main.MAX_IN_FLIGHT + 5):
        assert client.get("/api/auth/me").status_code == 401
    assert app.main._in_flight._value == app.main.MAX_IN_FLIGHT
