import logging

import jwt
import pytest

from app import security
from app.rate_limit import RateLimiter
from app.security import (
    SECRET_KEY,
    create_session_token,
    hash_password,
    read_session_token,
    verify_password,
)


def test_a_password_verifies_against_its_own_hash_only() -> None:
    hashed = hash_password("correct horse")
    assert verify_password("correct horse", hashed)
    assert not verify_password("wrong horse", hashed)


def test_an_unknown_user_never_verifies() -> None:
    assert not verify_password("anything at all", None)


def test_a_session_token_round_trips() -> None:
    assert read_session_token(create_session_token(42)) == 42


def test_a_token_without_a_numeric_subject_is_refused() -> None:
    token = jwt.encode({"sub": "ada", "exp": 9999999999}, SECRET_KEY, algorithm="HS256")
    assert read_session_token(token) is None


def test_the_secret_key_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "k" * 40)
    assert security._secret_key() == "k" * 40


def test_without_a_secret_key_a_random_one_is_used_and_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with caplog.at_level(logging.WARNING):
        first, second = security._secret_key(), security._secret_key()
    assert first != second
    assert len(first) >= 32
    assert "SECRET_KEY is not set" in caplog.text


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_the_limiter_allows_the_limit_then_says_how_long_to_wait() -> None:
    clock = FakeClock()
    limiter = RateLimiter(limit=2, window=60, clock=clock)
    assert limiter.hit("a") is None
    clock.now = 10
    assert limiter.hit("a") is None
    clock.now = 20
    assert limiter.hit("a") == 40  # the first hit leaves the window at 60


def test_the_window_slides() -> None:
    clock = FakeClock()
    limiter = RateLimiter(limit=1, window=60, clock=clock)
    assert limiter.hit("a") is None
    clock.now = 60
    assert limiter.hit("a") is None


def test_clients_are_counted_separately() -> None:
    limiter = RateLimiter(limit=1, window=60, clock=FakeClock())
    assert limiter.hit("a") is None
    assert limiter.hit("b") is None
    assert limiter.hit("a") is not None
