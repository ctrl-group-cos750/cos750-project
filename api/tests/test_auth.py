from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.security import SESSION_COOKIE, create_session_token

ADA = {"email": "Ada@Example.com", "password": "Correct horse 1", "displayName": "Ada"}


def register(client: TestClient, **changes: str) -> dict[str, object]:
    res = client.post("/api/auth/register", json={**ADA, **changes})
    assert res.status_code == 201, res.text
    body: dict[str, object] = res.json()
    return body


def session_cookie_header(res: object) -> str:
    headers = res.headers.get_list("set-cookie")  # type: ignore[attr-defined]
    [header] = [h for h in headers if h.startswith(f"{SESSION_COOKIE}=")]
    return str(header)


# Registering


def test_register_creates_the_account_and_logs_in(client: TestClient, db: Session) -> None:
    res = client.post("/api/auth/register", json=ADA)
    assert res.status_code == 201
    body = res.json()
    assert body == {
        "id": body["id"],
        "email": "ada@example.com",
        "displayName": "Ada",
        "isStaff": False,
        "avatar": None,
        "pictureUrl": None,
    }
    assert client.get("/api/auth/me").json()["email"] == "ada@example.com"


def test_the_session_cookie_is_locked_down(client: TestClient, db: Session) -> None:
    res = client.post("/api/auth/register", json=ADA)
    cookie = session_cookie_header(res).lower()
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie
    assert "max-age=1209600" in cookie  # 14 days (FR-1.2)


def test_passwords_are_stored_only_as_argon2_hashes(client: TestClient, db: Session) -> None:
    register(client)
    user = db.scalars(select(User)).one()
    assert user.password_hash.startswith("$argon2id$")
    assert ADA["password"] not in user.password_hash


def test_an_email_has_one_account_whatever_its_case(client: TestClient, db: Session) -> None:
    register(client)
    res = client.post("/api/auth/register", json={**ADA, "email": "ADA@example.COM"})
    assert res.status_code == 409
    assert res.json()["detail"] == "An account with this email already exists."


def test_the_display_name_is_trimmed(client: TestClient, db: Session) -> None:
    assert register(client, displayName="  Ada  ")["displayName"] == "Ada"


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "not-an-email"},
        {"password": "short"},
        {"password": "x" * 129},
        {"displayName": "   "},
        {"displayName": "x" * 51},
        {"isStaff": "true"},  # nobody makes themselves staff
    ],
    ids=["bad email", "short password", "long password", "blank name", "long name", "extra field"],
)
def test_register_rejects_invalid_input(
    client: TestClient, db: Session, changes: dict[str, str]
) -> None:
    res = client.post("/api/auth/register", json={**ADA, **changes})
    assert res.status_code == 422
    assert db.scalars(select(User)).first() is None


def test_register_refuses_a_cross_site_form_post(client: TestClient, db: Session) -> None:
    # A form on another site can send text/plain but not application/json (NFR-S6).
    import json

    res = client.post(
        "/api/auth/register", content=json.dumps(ADA), headers={"Content-Type": "text/plain"}
    )
    assert res.status_code == 422
    assert db.scalars(select(User)).first() is None


# Logging in and out


def test_login_with_the_right_password(client: TestClient, db: Session) -> None:
    register(client)
    client.cookies.clear()
    res = client.post(
        "/api/auth/login", json={"email": "ada@example.com", "password": ADA["password"]}
    )
    assert res.status_code == 200
    assert res.json()["displayName"] == "Ada"
    assert "httponly" in session_cookie_header(res).lower()
    assert client.get("/api/auth/me").status_code == 200


@pytest.mark.parametrize(
    "credentials",
    [
        {"email": "ada@example.com", "password": "wrong password"},
        {"email": "nobody@example.com", "password": "Correct horse 1"},
    ],
    ids=["wrong password", "unknown email"],
)
def test_login_failures_all_look_the_same(
    client: TestClient, db: Session, credentials: dict[str, str]
) -> None:
    register(client)
    client.cookies.clear()
    res = client.post("/api/auth/login", json=credentials)
    assert res.status_code == 401
    assert res.json()["detail"] == "Email or password is incorrect."
    assert SESSION_COOKIE not in client.cookies


def test_logout_ends_the_session(client: TestClient, db: Session) -> None:
    register(client)
    res = client.post("/api/auth/logout")
    assert res.status_code == 204
    assert "max-age=0" in session_cookie_header(res).lower()
    assert client.get("/api/auth/me").status_code == 401


def test_logout_works_without_a_session(client: TestClient, db: Session) -> None:
    assert client.post("/api/auth/logout").status_code == 204


# Sessions


def test_me_needs_a_session(client: TestClient, db: Session) -> None:
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    assert res.json()["detail"] == "Log in to continue."


@pytest.mark.parametrize(
    "token",
    [
        "not-a-token",
        create_session_token(1, 0)[:-4] + "AAAA",  # signature tampered with
        create_session_token(1, 0, now=datetime.now(UTC) - timedelta(days=15)),  # expired
        create_session_token(999, 0),  # user no longer exists
        create_session_token(1, 1),  # a session version the user never had
    ],
    ids=["garbage", "tampered", "expired", "deleted user", "wrong version"],
)
def test_invalid_sessions_are_refused(client: TestClient, db: Session, token: str) -> None:
    register(client)  # user 1 exists
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, token)
    assert client.get("/api/auth/me").status_code == 401


# Stolen cookies


def test_a_copied_cookie_stops_working_after_logout(client: TestClient, db: Session) -> None:
    register(client)
    stolen = client.cookies[SESSION_COOKIE]
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.set(SESSION_COOKIE, stolen)
    assert client.get("/api/auth/me").status_code == 401


def test_logging_out_ends_the_session_on_every_device(client: TestClient, db: Session) -> None:
    register(client)
    client.cookies.clear()
    credentials = {"email": "ada@example.com", "password": ADA["password"]}
    laptop = client.post("/api/auth/login", json=credentials).cookies[SESSION_COOKIE]
    phone = client.post("/api/auth/login", json=credentials).cookies[SESSION_COOKIE]
    client.cookies.set(SESSION_COOKIE, phone)
    client.post("/api/auth/logout")
    client.cookies.set(SESSION_COOKIE, laptop)
    assert client.get("/api/auth/me").status_code == 401


def test_logging_in_again_after_logout_works(client: TestClient, db: Session) -> None:
    register(client)
    client.post("/api/auth/logout")
    res = client.post(
        "/api/auth/login", json={"email": "ada@example.com", "password": ADA["password"]}
    )
    assert res.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


# Rate limits (NFR-S6)

WRONG = {"email": "ada@example.com", "password": "wrong password"}


def test_guessing_one_account_is_rate_limited(client: TestClient, db: Session) -> None:
    for _ in range(10):
        assert client.post("/api/auth/login", json=WRONG).status_code == 401
    res = client.post("/api/auth/login", json=WRONG)
    assert res.status_code == 429
    assert res.json()["detail"] == "Too many attempts. Wait a minute and try again."
    assert 0 < int(res.headers["Retry-After"]) <= 60


def test_one_locked_account_does_not_block_others_on_the_same_address(
    client: TestClient, db: Session
) -> None:
    # A campus shares one public address: one student's typos must not lock out the class.
    for _ in range(11):
        client.post("/api/auth/login", json=WRONG)
    other = {"email": "grace@example.com", "password": "wrong password"}
    assert client.post("/api/auth/login", json=other).status_code == 401


def test_spraying_many_accounts_from_one_address_is_rate_limited(
    client: TestClient, db: Session
) -> None:
    for n in range(60):
        body = {"email": f"student{n}@example.com", "password": "wrong password"}
        assert client.post("/api/auth/login", json=body).status_code == 401
    assert client.post("/api/auth/login", json=WRONG).status_code == 429


def test_register_is_rate_limited(client: TestClient, db: Session) -> None:
    for n in range(20):
        register(client, email=f"student{n}@example.com")
    res = client.post("/api/auth/register", json={**ADA, "email": "student20@example.com"})
    assert res.status_code == 429


def test_a_faked_cloudflare_header_does_not_dodge_the_limit(
    client: TestClient, db: Session
) -> None:
    # The test client is not a Cloudflare address, so CF-Connecting-IP must be ignored.
    for n in range(10):
        headers = {"CF-Connecting-IP": f"203.0.113.{n}"}
        client.post("/api/auth/login", json=WRONG, headers=headers)
    res = client.post("/api/auth/login", json=WRONG, headers={"CF-Connecting-IP": "203.0.113.99"})
    assert res.status_code == 429
