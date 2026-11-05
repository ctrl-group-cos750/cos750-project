"""The staff portal's "Staff members" page (GET/POST/DELETE /api/staff/members): a team member
makes an existing account staff by email, or takes the access away, but never their own."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User

PASSWORD = "Correct horse 1"  # noqa: S105 (a test account)


def register(client: TestClient, email: str, name: str) -> None:
    body = {"email": email, "password": PASSWORD, "displayName": name}
    assert client.post("/api/auth/register", json=body).status_code == 201


def make_staff(db: Session, email: str) -> int:
    user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.is_staff = True
    db.commit()
    return user.id


def log_in(client: TestClient, email: str) -> None:
    client.cookies.clear()
    body = {"email": email, "password": PASSWORD}
    assert client.post("/api/auth/login", json=body).status_code == 200


@pytest.fixture
def team(client: TestClient, db: Session) -> dict[str, int]:
    """Grace is staff and logged in; Ada and Alan are students."""
    register(client, "ada@example.com", "Ada")
    register(client, "alan@example.com", "Alan")
    register(client, "grace@example.com", "Grace")
    ids = {"grace": make_staff(db, "grace@example.com")}
    for name in ("ada", "alan"):
        user = db.scalar(select(User).where(User.email == f"{name}@example.com"))
        assert user is not None
        ids[name] = user.id
    return ids


def is_staff(db: Session, user_id: int) -> bool:
    db.expire_all()
    user = db.get(User, user_id)
    assert user is not None
    return user.is_staff


def test_students_and_guests_cannot_use_it(client: TestClient, team: dict[str, int]) -> None:
    log_in(client, "ada@example.com")
    assert client.get("/api/staff/members").status_code == 403
    assert client.post("/api/staff/members", json={"email": "ada@example.com"}).status_code == 403
    assert client.delete(f"/api/staff/members/{team['grace']}").status_code == 403
    client.cookies.clear()
    assert client.get("/api/staff/members").status_code == 401


def test_lists_only_staff(client: TestClient, team: dict[str, int]) -> None:
    response = client.get("/api/staff/members")
    assert response.status_code == 200
    assert response.json() == [
        {"id": team["grace"], "email": "grace@example.com", "displayName": "Grace"}
    ]


def test_promote_by_email_then_they_can_use_staff_pages(
    client: TestClient, db: Session, team: dict[str, int]
) -> None:
    response = client.post("/api/staff/members", json={"email": "  ADA@Example.com "})
    assert response.status_code == 200
    assert response.json() == {"id": team["ada"], "email": "ada@example.com", "displayName": "Ada"}
    assert is_staff(db, team["ada"])
    # Twice is harmless.
    assert client.post("/api/staff/members", json={"email": "ada@example.com"}).status_code == 200

    log_in(client, "ada@example.com")
    assert client.get("/api/auth/me").json()["isStaff"] is True
    assert client.get("/api/staff/videos").status_code == 200


def test_promoting_an_unknown_email_says_to_register(
    client: TestClient, team: dict[str, int]
) -> None:
    response = client.post("/api/staff/members", json={"email": "nobody@example.com"})
    assert response.status_code == 404
    assert "register" in response.json()["detail"]


def test_remove_takes_access_away_at_once(
    client: TestClient, db: Session, team: dict[str, int]
) -> None:
    client.post("/api/staff/members", json={"email": "ada@example.com"})
    log_in(client, "ada@example.com")
    assert client.get("/api/staff/videos").status_code == 200

    # Ada stays logged in while Grace removes her: her very next request is refused.
    ada_cookies = dict(client.cookies)
    log_in(client, "grace@example.com")
    assert client.delete(f"/api/staff/members/{team['ada']}").status_code == 204
    assert not is_staff(db, team["ada"])
    client.cookies.clear()
    for name, value in ada_cookies.items():
        client.cookies.set(name, value)
    assert client.get("/api/staff/videos").status_code == 403


def test_nobody_can_remove_themselves(
    client: TestClient, db: Session, team: dict[str, int]
) -> None:
    response = client.delete(f"/api/staff/members/{team['grace']}")
    assert response.status_code == 409
    assert "Ask another team member" in response.json()["detail"]
    assert is_staff(db, team["grace"])


def test_removing_a_student_or_a_missing_user_is_404(
    client: TestClient, team: dict[str, int]
) -> None:
    assert client.delete(f"/api/staff/members/{team['alan']}").status_code == 404
    assert client.delete("/api/staff/members/9999").status_code == 404


@pytest.mark.parametrize("body", [{}, {"email": "a" * 321}, {"email": "a@b.co", "isStaff": True}])
def test_bad_bodies_are_refused(client: TestClient, team: dict[str, int], body: object) -> None:
    assert client.post("/api/staff/members", json=body).status_code == 422
