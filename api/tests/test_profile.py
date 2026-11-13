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


def test_the_password_change_documents_every_answer_it_gives(client: TestClient) -> None:
    # The published schema matches the real contract, so the generated types do too (NFR-M2).
    answers = client.get("/api/openapi.json").json()["paths"]["/api/me/password"]["post"]
    assert set(answers["responses"]) == {"204", "400", "422", "429"}


# --- An uploaded picture (FR-1.6) ---------------------------------------------------------------

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 64


def data_url(kind: str, raw: bytes) -> str:
    import base64

    return f"data:{kind};base64,{base64.b64encode(raw).decode()}"


@pytest.mark.parametrize(
    ("kind", "raw"), [("image/png", PNG), ("image/jpeg", JPEG), ("image/webp", WEBP)]
)
def test_a_student_can_upload_their_own_picture(
    client: TestClient, db: Session, kind: str, raw: bytes
) -> None:
    log_in(client)
    client.put("/api/me/avatar", json={"avatar": "tree"})
    response = client.put("/api/me/picture", json={"image": data_url(kind, raw)})
    assert response.status_code == 200
    me = response.json()
    assert me["avatar"] is None  # the upload replaces the chosen picture
    assert me["pictureUrl"].startswith("/api/me/picture?v=")
    image = client.get(me["pictureUrl"])
    assert image.status_code == 200
    assert image.content == raw
    assert image.headers["content-type"] == kind
    assert image.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in image.headers["content-security-policy"]
    assert image.headers["cache-control"].startswith("private")


def test_choosing_one_of_the_teams_pictures_deletes_the_upload(
    client: TestClient, db: Session
) -> None:
    log_in(client)
    client.put("/api/me/picture", json={"image": data_url("image/png", PNG)})
    assert client.put("/api/me/avatar", json={"avatar": "star"}).json()["pictureUrl"] is None
    assert client.get("/api/me/picture").status_code == 404


def test_removing_the_picture_deletes_it(client: TestClient, db: Session) -> None:
    user_id = log_in(client)
    client.put("/api/me/picture", json={"image": data_url("image/png", PNG)})
    assert client.delete("/api/me/picture").json()["pictureUrl"] is None
    assert client.get("/api/me/picture").status_code == 404
    db.expire_all()
    user = db.get(User, user_id)
    assert user is not None
    assert user.picture is None


@pytest.mark.parametrize(
    "image",
    [
        data_url("image/svg+xml", b"<svg onload='alert(1)'/>"),  # scripts: never kept
        data_url("text/html", b"<script>alert(1)</script>"),
        data_url("image/png", b"<script>alert(1)</script>"),  # claims PNG, isn't one
        data_url("image/png", JPEG),  # claims PNG, is a JPEG
        "data:image/png;base64,not base64!!",
        "https://evil.example/me.png",
        data_url("image/png", PNG + b"\x00" * 200_001),  # too big
    ],
)
def test_only_small_real_pictures_are_kept(client: TestClient, db: Session, image: str) -> None:
    log_in(client)
    assert client.put("/api/me/picture", json={"image": image}).status_code in (400, 422)
    assert client.get("/api/auth/me").json()["pictureUrl"] is None


def test_pictures_need_a_login(client: TestClient, db: Session) -> None:
    assert client.get("/api/me/picture").status_code == 401
    assert (
        client.put("/api/me/picture", json={"image": data_url("image/png", PNG)}).status_code == 401
    )
    assert client.delete("/api/me/picture").status_code == 401


def test_a_picture_goes_with_the_account(client: TestClient, db: Session) -> None:
    """Only the student's own session can fetch it: the URL has no user id to change."""
    log_in(client)
    url = client.put("/api/me/picture", json={"image": data_url("image/png", PNG)}).json()[
        "pictureUrl"
    ]
    client.post("/api/auth/logout")
    other = {"email": "grace@example.com", "password": PASSWORD, "displayName": "Grace"}
    assert client.post("/api/auth/register", json=other).status_code == 201
    assert client.get(url).status_code == 404


def test_uploads_are_limited_to_ten_a_minute(client: TestClient, db: Session) -> None:
    log_in(client)
    image = data_url("image/png", PNG)
    for _ in range(10):
        assert client.put("/api/me/picture", json={"image": image}).status_code == 200
    assert client.put("/api/me/picture", json={"image": image}).status_code == 429
