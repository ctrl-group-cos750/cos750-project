"""Attacks from the security review (SE document §14), kept as regression tests.

scripts/security-probe.py runs the same kinds of attack against a deployed copy.
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.security import SESSION_COOKIE

ADA = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}


def b64(data: dict[str, Any] | bytes) -> str:
    raw = data if isinstance(data, bytes) else json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def unb64(part: str) -> dict[str, Any]:
    decoded: dict[str, Any] = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    return decoded


def signed(header: dict[str, Any], claims: dict[str, Any], key: bytes, digest: Any) -> str:
    signing = f"{b64(header)}.{b64(claims)}"
    return f"{signing}.{b64(hmac.new(key, signing.encode(), digest).digest())}"


@pytest.fixture
def ada(client: TestClient, db: Session) -> str:
    """Ada's session token."""
    client.post("/api/auth/register", json=ADA)
    token: str = client.cookies[SESSION_COOKIE]
    client.cookies.clear()
    return token


def me(client: TestClient, token: str) -> int:
    client.cookies.set(SESSION_COOKIE, token)
    status: int = client.get("/api/auth/me").status_code
    client.cookies.clear()
    return status


# Forged tokens


def forgeries(token: str) -> dict[str, str]:
    head, payload, signature = token.split(".")
    claims = unb64(payload)
    other = {**claims, "sub": "2"}
    sha256, sha512 = hashlib.sha256, hashlib.sha512
    return {
        "alg none": f"{b64({'alg': 'none'})}.{b64(other)}.",
        "subject swapped, signature kept": f"{head}.{b64(other)}.{signature}",
        "version raised, signature kept": f"{head}.{b64({**claims, 'ver': 1})}.{signature}",
        "expiry extended, signature kept": f"{head}.{b64({**claims, 'exp': 10**11})}.{signature}",
        "signature removed": f"{head}.{payload}.",
        "HS512 with an empty key": signed({"alg": "HS512"}, other, b"", sha512),
        "RS256 header, HMAC signature": signed({"alg": "RS256"}, other, b"secret", sha256),
        "kid pointing at /dev/null": signed(
            {"alg": "HS256", "kid": "/dev/null"}, other, b"", sha256
        ),
        "jku pointing elsewhere": signed(
            {"alg": "HS256", "jku": "https://evil.example/keys"}, other, b"x", sha256
        ),
        "embedded jwk": signed(
            {"alg": "HS256", "jwk": {"kty": "oct", "k": b64(b"x")}}, other, b"x", sha256
        ),
    }


@pytest.mark.parametrize(
    "name",
    list(forgeries(f"{b64({'alg': 'HS256'})}.{b64({'sub': '1', 'ver': 0, 'exp': 1})}.x")),
)
def test_forged_tokens_are_refused(client: TestClient, ada: str, name: str) -> None:
    client.post("/api/auth/register", json={**ADA, "email": "grace@example.com"})  # user 2
    client.cookies.clear()
    assert me(client, forgeries(ada)[name]) == 401


def test_the_genuine_token_works(client: TestClient, ada: str) -> None:
    assert me(client, ada) == 200


def test_the_token_carries_no_personal_data(ada: str) -> None:
    assert set(unb64(ada.split(".")[1])) == {"sub", "ver", "iat", "exp"}


def test_an_authorization_header_is_not_a_second_way_in(client: TestClient, ada: str) -> None:
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {ada}"})
    assert res.status_code == 401


def test_two_session_cookies_never_fail_open(client: TestClient, ada: str) -> None:
    res = client.get("/api/auth/me", headers={"Cookie": f"{SESSION_COOKIE}=x; {SESSION_COOKIE}=y"})
    assert res.status_code == 401


# Requests the API should refuse cleanly


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/auth/logout"),
        ("GET", "/api/auth/login"),
        ("PUT", "/api/auth/me"),
        ("DELETE", "/api/auth/me"),
        ("PATCH", "/api/auth/register"),
    ],
)
def test_methods_that_are_not_routes(
    client: TestClient, db: Session, method: str, path: str
) -> None:
    assert client.request(method, path).status_code == 405


HOSTILE: dict[str, Any] = {
    "SQL in email": {"email": "' OR '1'='1'--@x.com", "password": "x"},
    "SQL in password": {"email": "ada@example.com", "password": "' OR '1'='1"},
    "null byte in password": {"email": "ada@example.com", "password": "abc\u0000def"},
    "null byte in email": {"email": "a\u0000da@example.com", "password": "x"},
    "email as a list": {"email": ["ada@example.com"], "password": "x"},
    "password as an object": {"email": "ada@example.com", "password": {"$ne": ""}},
    "password as true": {"email": "ada@example.com", "password": True},
    "missing fields": {},
    "200 kB password": {"email": "ada@example.com", "password": "a" * 200_000},
}


@pytest.mark.parametrize("name", list(HOSTILE))
def test_hostile_login_input_is_refused_not_crashed(
    client: TestClient, ada: str, name: str
) -> None:
    res = client.post("/api/auth/login", json=HOSTILE[name])
    assert res.status_code in (401, 422)
    assert SESSION_COOKIE not in client.cookies


def test_deeply_nested_json_is_refused_not_crashed(client: TestClient, db: Session) -> None:
    # Python 3.12 parses this; the default error handler then crashed echoing it back (500).
    nested = "[" * 5000 + '"ada@example.com"' + "]" * 5000
    res = client.post(
        "/api/auth/login",
        content=f'{{"email": {nested}, "password": "x"}}',
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code in (400, 422)


def test_validation_errors_never_repeat_what_was_sent(client: TestClient, db: Session) -> None:
    secret = "my real password, too long " * 10
    res = client.post("/api/auth/register", json={**ADA, "password": secret})
    assert res.status_code == 422
    assert secret not in res.text
    assert res.json()["detail"] == [
        {
            "loc": ["body", "password"],
            "msg": "String should have at most 128 characters",
            "type": "string_too_long",
        }
    ]


def test_broken_json_is_refused_without_internals(client: TestClient, db: Session) -> None:
    res = client.post(
        "/api/auth/login",
        content=b'{"email": "ada@example.com", "password": ',
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 422
    assert "Traceback" not in res.text


# Account confusion


@pytest.mark.parametrize(
    "email",
    ["ADA@EXAMPLE.COM", "  ada@example.com  ", "Ada@Example.com"],
    ids=["upper case", "spaces", "mixed case"],
)
def test_the_same_mailbox_cannot_get_a_second_account(
    client: TestClient, ada: str, email: str
) -> None:
    res = client.post("/api/auth/register", json={**ADA, "email": email})
    assert res.status_code == 409


def test_nobody_chooses_their_own_user_id(client: TestClient, ada: str) -> None:
    res = client.post("/api/auth/register", json={**ADA, "email": "grace@example.com", "id": 1})
    assert res.status_code == 422


def test_an_expired_token_with_a_valid_signature_is_refused(client: TestClient, ada: str) -> None:
    from datetime import UTC, datetime, timedelta

    from app.security import create_session_token

    old = create_session_token(1, 0, now=datetime.now(UTC) - timedelta(days=14, seconds=1))
    assert me(client, old) == 401
    assert time.time() > unb64(old.split(".")[1])["exp"]


# Responses and tokens


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/api/health", None),
        ("GET", "/api/auth/me", None),
        ("POST", "/api/auth/login", {"email": "ada@example.com", "password": "Correct horse 1"}),
        ("POST", "/api/auth/login", {"email": "ada@example.com", "password": "wrong"}),
        ("POST", "/api/auth/register", {"email": "bad"}),
    ],
    ids=["health", "me", "login", "failed login", "validation error"],
)
def test_no_api_response_is_cached(
    client: TestClient, ada: str, method: str, path: str, body: dict[str, str] | None
) -> None:
    client.cookies.set(SESSION_COOKIE, ada)
    res = client.request(method, path, json=body)
    assert res.headers["cache-control"] == "no-store"


def test_a_token_lasts_exactly_fourteen_days(ada: str) -> None:
    claims = unb64(ada.split(".")[1])
    assert claims["exp"] - claims["iat"] == 14 * 24 * 60 * 60


@pytest.mark.parametrize(
    "lookalike",
    ["\uff41da@example.com", "\u0430da@example.com", "ada@exa\u0335mple.com"],
    ids=["fullwidth a", "cyrillic a", "combining mark"],
)
def test_a_lookalike_email_never_reaches_the_real_account(
    client: TestClient, ada: str, lookalike: str
) -> None:
    res = client.post(
        "/api/auth/register", json={**ADA, "email": lookalike, "password": "Other pw 12!"}
    )
    if res.status_code == 201:
        assert res.json()["email"] != "ada@example.com"
    else:
        assert res.status_code in (409, 422)
    client.cookies.clear()
    wrong = client.post(
        "/api/auth/login", json={"email": "ada@example.com", "password": "Other pw 12!"}
    )
    assert wrong.status_code == 401
    right = client.post(
        "/api/auth/login", json={"email": "ada@example.com", "password": ADA["password"]}
    )
    assert right.status_code == 200


# Round four: hidden characters, cookie prefix, switching accounts


@pytest.mark.parametrize(
    "name",
    [
        "Ada\u0000",
        "Ada\nAdmin",
        "Ada\u0007",
        "Ada\u202egnp.exe",
        "A\u200bda",
        "\ufeffAda",
        "\u200b",
    ],
    ids=[
        "NUL",
        "newline",
        "bell",
        "right-to-left override",
        "zero-width space",
        "BOM",
        "only invisible",
    ],
)
def test_display_names_with_hidden_characters_are_refused(
    client: TestClient, db: Session, name: str
) -> None:
    # A NUL used to reach Postgres, which refuses it, and the API answered 500.
    res = client.post("/api/auth/register", json={**ADA, "displayName": name})
    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == ["body", "displayName"]


@pytest.mark.parametrize(
    "name",
    ["Zoë O'Brien-Nkosi", "李小龍", "Ada 🙂", "Thabo (TA)"],
    ids=["accents", "CJK", "emoji", "brackets"],
)
def test_ordinary_names_in_any_language_are_accepted(
    client: TestClient, db: Session, name: str
) -> None:
    res = client.post("/api/auth/register", json={**ADA, "displayName": name})
    assert res.status_code == 201
    assert res.json()["displayName"] == name


def test_names_are_stored_in_one_unicode_form(client: TestClient, db: Session) -> None:
    res = client.post("/api/auth/register", json={**ADA, "displayName": "Zoë"})
    assert res.json()["displayName"] == "Zoë"


def test_the_session_cookie_cannot_be_planted_by_another_subdomain(
    client: TestClient, db: Session
) -> None:
    res = client.post("/api/auth/register", json=ADA)
    header = next(h for h in res.headers.get_list("set-cookie") if h.startswith("__Host-"))
    assert header.startswith("__Host-session=")
    assert "domain=" not in header.lower()
    assert "path=/" in header.lower()
    assert "secure" in header.lower()


def test_logging_in_as_someone_else_switches_the_session(client: TestClient, ada: str) -> None:
    client.post(
        "/api/auth/register", json={**ADA, "email": "grace@example.com", "displayName": "G"}
    )
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, ada)
    res = client.post(
        "/api/auth/login", json={"email": "grace@example.com", "password": ADA["password"]}
    )
    assert res.json()["displayName"] == "G"
    assert client.get("/api/auth/me").json()["displayName"] == "G"
    assert me(client, ada) == 200  # Ada's own session is untouched


def test_duplicate_json_keys_do_not_confuse_login(client: TestClient, ada: str) -> None:
    res = client.post(
        "/api/auth/login",
        content=b'{"email": "nobody@example.com", "email": "ada@example.com", "password": "wrong!"}',
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 401


def test_an_unknown_api_route_is_a_plain_404(client: TestClient, db: Session) -> None:
    res = client.get("/api/admin")
    assert res.status_code == 404
    assert res.json() == {"detail": "Not Found"}


@pytest.mark.parametrize(
    ("setting", "on"), [(None, True), ("on", True), ("off", False), (" OFF ", False)]
)
def test_api_docs_can_be_switched_off_for_production(setting: str | None, on: bool) -> None:
    from app.main import docs_urls

    urls = docs_urls(setting)
    assert (urls["docs_url"] == "/api/docs") is on
    assert (urls["openapi_url"] == "/api/openapi.json") is on
    assert urls["redoc_url"] is None
