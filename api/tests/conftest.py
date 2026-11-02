from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import StaticPool

import app.main
from app.main import app as fastapi_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(fastapi_app) as test_client:
        yield test_client


@pytest.fixture
def working_db(monkeypatch: pytest.MonkeyPatch) -> Engine:
    """An in-memory SQLite engine, so tests never depend on a running Postgres."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(app.main, "engine", engine)
    return engine


@pytest.fixture
def unreachable_db(monkeypatch: pytest.MonkeyPatch) -> Engine:
    """An engine pointed at a port nothing listens on."""
    engine = create_engine(
        "postgresql+psycopg://ctrl:ctrl@127.0.0.1:1/ctrl", connect_args={"connect_timeout": 1}
    )
    monkeypatch.setattr(app.main, "engine", engine)
    return engine
