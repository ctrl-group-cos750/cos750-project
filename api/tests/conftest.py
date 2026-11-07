import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.main
from app.db import Base, get_session
from app.main import app as fastapi_app
from app.rate_limit import login_account_limiter, login_address_limiter, register_limiter
from app.routers.events import events_limiter
from app.routers.profile import password_change_limiter

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture
def client() -> Iterator[TestClient]:
    # https, because the session cookie is Secure and is never sent over plain http.
    with TestClient(fastapi_app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def fresh_rate_limits() -> None:
    login_account_limiter.reset()
    login_address_limiter.reset()
    register_limiter.reset()
    events_limiter.reset()
    password_change_limiter.reset()


@pytest.fixture
def db() -> Iterator[Session]:
    """Routes get a database with every table, empty for each test.

    In-memory SQLite by default. With TEST_DATABASE_URL set (CI does), a real Postgres instead,
    which catches what SQLite allows and Postgres refuses, such as NUL characters in text.
    """
    if TEST_DATABASE_URL:
        engine = create_engine(TEST_DATABASE_URL)
        Base.metadata.drop_all(engine)
    else:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    def override() -> Iterator[Session]:
        with sessions() as session:
            yield session

    fastapi_app.dependency_overrides[get_session] = override
    with sessions() as session:
        yield session
    fastapi_app.dependency_overrides.clear()
    if TEST_DATABASE_URL:
        Base.metadata.drop_all(engine)
    engine.dispose()


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
