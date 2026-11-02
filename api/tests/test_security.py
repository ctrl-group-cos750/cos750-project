import logging

import jwt
import pytest
from fastapi import HTTPException, Request

from app import security
from app.rate_limit import RateLimiter, client_ip, is_cloudflare
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
    assert read_session_token(create_session_token(42, version=3)) == (42, 3)


@pytest.mark.parametrize(
    "claims",
    [
        {"sub": "ada", "ver": 0, "exp": 9999999999},  # not a user ID
        {"sub": "1", "exp": 9999999999},  # no session version
        {"sub": "1", "ver": "0", "exp": 9999999999},  # version not a number
        {"sub": "1", "ver": 0},  # never expires
    ],
    ids=["named subject", "no version", "text version", "no expiry"],
)
def test_malformed_tokens_are_refused(claims: dict[str, object]) -> None:
    assert read_session_token(jwt.encode(claims, SECRET_KEY, algorithm="HS256")) is None


def test_a_token_with_alg_none_is_refused() -> None:
    token = jwt.encode({"sub": "1", "ver": 0, "exp": 9999999999}, None, algorithm="none")
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


def request_from(peer: str, headers: dict[str, str] | None = None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "client": (peer, 1234), "headers": raw})


def test_behind_cloudflare_the_students_own_address_is_used() -> None:
    req = request_from("104.22.45.26", {"CF-Connecting-IP": "102.132.239.1"})
    assert client_ip(req) == "102.132.239.1"


def test_cloudflare_ipv6_edges_are_recognised() -> None:
    req = request_from("2606:4700:3034::ac43:ca46", {"CF-Connecting-IP": "102.132.239.1"})
    assert client_ip(req) == "102.132.239.1"


def test_someone_bypassing_cloudflare_cannot_choose_their_address() -> None:
    req = request_from("198.51.100.7", {"CF-Connecting-IP": "203.0.113.1"})
    assert client_ip(req) == "198.51.100.7"


def test_a_request_without_the_header_uses_the_connecting_address() -> None:
    assert client_ip(request_from("104.22.45.26")) == "104.22.45.26"


def test_a_peer_that_is_not_an_address_is_never_cloudflare() -> None:
    assert not is_cloudflare("testclient")


def test_the_limiter_refuses_with_retry_after() -> None:
    limiter = RateLimiter(limit=1, window=60, clock=FakeClock())
    limiter.check("a")
    with pytest.raises(HTTPException) as refused:
        limiter.check("a")
    assert refused.value.status_code == 429
    assert refused.value.headers == {"Retry-After": "60"}
