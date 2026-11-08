"""The student's own profile (FR-1.5, FR-1.6): choosing a picture and changing the password."""

import re
from pathlib import Path
from typing import Any, get_args

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User
from app.schemas.profile import Avatar

PASSWORD = "Correct horse 1"  # noqa: S105 (a test account)
NEW = "Purple kettle 42"
STUDENT = {"email": "ada@example.com", "password": PASSWORD, "displayName": "Ada"}


def log_in(client: TestClient) -> int:
    assert client.post("/api/auth/register", json=STUDENT).status_code == 201
    return int(client.get("/api/auth/me").json()["id"])


def change(client: TestClient, current: str = PASSWORD, new: str = NEW) -> Any:
    return client.post("/api/me/password", json={"currentPassword": current, "newPassword": new})


def test_profile_changes_need_a_login(client: TestClient, db: Session) -> None:
    assert client.put("/api/me/avatar", json={"avatar": "tree"}).status_code == 401
    assert change(client).status_code == 401


# --- Profile picture (FR-1.6) -------------------------------------------------------------------


def test_a_new_student_has_no_picture(client: TestClient, db: Session) -> None:
    log_in(client)
    assert client.get("/api/auth/me").json()["avatar"] is None


def test_choosing_a_picture_is_saved_and_shown(client: TestClient, db: Session) -> None:
    log_in(client)
    response = client.put("/api/me/avatar", json={"avatar": "tree"})
    assert response.status_code == 200
    assert response.json()["avatar"] == "tree"
    assert client.get("/api/auth/me").json()["avatar"] == "tree"
    assert client.put("/api/me/avatar", json={"avatar": None}).json()["avatar"] is None


@pytest.mark.parametrize("avatar", ["https://evil.example/me.png", "../../etc/passwd", "", 3])
def test_only_the_teams_pictures_can_be_chosen(
    client: TestClient, db: Session, avatar: object
) -> None:
    log_in(client)
    assert client.put("/api/me/avatar", json={"avatar": avatar}).status_code == 422
    assert client.get("/api/auth/me").json()["avatar"] is None


# --- Changing the password (FR-1.5) -------------------------------------------------------------


def test_changing_the_password_keeps_this_session_and_ends_the_others(
    client: TestClient, db: Session
) -> None:
    log_in(client)
    other = TestClient(client.app, base_url="https://testserver")  # the same student, elsewhere
    login = {"email": STUDENT["email"], "password": PASSWORD}
    assert other.post("/api/auth/login", json=login).status_code == 200

    assert change(client).status_code == 204
    assert client.get("/api/auth/me").status_code == 200  # still logged in here
    assert other.get("/api/auth/me").status_code == 401  # logged out everywhere else

    assert client.post("/api/auth/login", json=login).status_code == 401  # the old one is gone
    login["password"] = NEW
    assert client.post("/api/auth/login", json=login).status_code == 200


def test_a_wrong_current_password_is_refused(client: TestClient, db: Session) -> None:
    user_id = log_in(client)
    before = db.get_one(User, user_id).password_hash
    response = change(client, current="Not my password 9")
    assert response.status_code == 400
    assert response.json()["detail"] == "Your current password is not right."
    db.expire_all()
    assert db.get_one(User, user_id).password_hash == before


@pytest.mark.parametrize(
    ("new", "message"),
    [
        ("short1!", "at least 8 characters"),
        ("alllowercase 1", "uppercase"),
        ("Ada is great 1", "name or email"),
        (PASSWORD, "not the one you have now"),
    ],
)
def test_the_new_password_follows_the_rules(
    client: TestClient, db: Session, new: str, message: str
) -> None:
    log_in(client)
    response = change(client, new=new)
    assert response.status_code == 400
    assert message in response.json()["detail"]


def test_guessing_the_current_password_is_slowed(client: TestClient, db: Session) -> None:
    log_in(client)
    codes = [change(client, current=f"Guess number {n}!").status_code for n in range(11)]
    assert codes[:10] == [400] * 10
    assert codes[10] == 429


def test_the_api_and_the_app_offer_the_same_pictures() -> None:
    """The ids in app/schemas/profile.py and web/src/components/avatars.ts must match, or a picture
    the app offers would be refused, or one the API allows would draw nothing."""
    source = (Path(__file__).parents[2] / "web/src/components/avatars.ts").read_text()
    found = re.search(r"AVATARS = \[([^\]]*)\]", source)
    assert found is not None
    assert re.findall(r"'([a-z]+)'", found.group(1)) == list(get_args(Avatar))
