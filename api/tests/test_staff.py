"""Staff media uploads and the video editor's API (app/routers/staff.py): who may use them, what
gets stored where, and that students then see the video through GET /api/videos/{id}."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import media
from app.models import Activity, Attempt, Hint, User

STAFF = {"email": "staff@example.com", "password": "Correct horse 1", "displayName": "Staff"}
STUDENT = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}
MP4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64
VTT = b"WEBVTT\n\n00:00.000 --> 00:02.000\nHello\n"


@pytest.fixture(autouse=True)
def media_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path))
    return tmp_path


def log_in(client: TestClient, db: Session, who: dict[str, str], staff: bool) -> None:
    assert client.post("/api/auth/register", json=who).status_code == 201
    if staff:
        user = db.scalar(select(User).where(User.email == who["email"]))
        assert user is not None
        user.is_staff = True
        db.commit()


def upload(client: TestClient, kind: str, body: bytes, content_type: str) -> Any:
    return client.post(
        f"/api/staff/media?kind={kind}", content=body, headers={"Content-Type": content_type}
    )


def uploaded_paths(client: TestClient) -> tuple[str, str]:
    video = upload(client, "video", MP4, "video/mp4")
    captions = upload(client, "captions", VTT, "text/vtt")
    assert video.status_code == 201, video.text
    assert captions.status_code == 201, captions.text
    return video.json()["path"], captions.json()["path"]


def checkpoint(at: float, prompt: str = "Which leaves first?", **extra: Any) -> dict[str, Any]:
    return {
        "atSeconds": at,
        "question": {
            "prompt": prompt,
            "options": [{"id": "a", "label": "A"}, {"id": "c", "label": "C"}],
            "correct": "a",
            "feedback": {"c": "That's a stack."},
        },
        "hints": [{"level": 1, "body": "FIFO"}, {"level": 2, "body": "The oldest one"}],
        **extra,
    }


def video_body(paths: tuple[str, str], checkpoints: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "title": "Meet BFS",
        "mediaPath": paths[0],
        "captionsPath": paths[1],
        "transcript": "Line one.\nLine two.",
        "durationSeconds": 60,
        "checkpoints": checkpoints,
    }


# --- Who may use it ----------------------------------------------------------------------------


def test_students_get_403_and_guests_401(client: TestClient, db: Session) -> None:
    assert client.get("/api/staff/videos").status_code == 401
    log_in(client, db, STUDENT, staff=False)
    assert client.get("/api/staff/videos").status_code == 403
    assert upload(client, "video", MP4, "video/mp4").status_code == 403


# --- Uploads -----------------------------------------------------------------------------------


def test_upload_stores_the_file_on_the_volume(
    client: TestClient, db: Session, media_dir: Path
) -> None:
    log_in(client, db, STAFF, staff=True)
    res = upload(client, "video", MP4, "video/mp4")
    assert res.status_code == 201
    path = res.json()["path"]
    assert path.startswith("/media/videos/")
    assert path.endswith(".mp4")
    stored = media_dir / path.removeprefix("/media/")
    assert stored.read_bytes() == MP4
    assert stored.stat().st_mode & 0o777 == 0o644  # nginx, another user, can read it
    assert [p.name for p in stored.parent.iterdir()] == [stored.name]  # no .part left behind


@pytest.mark.parametrize(
    ("kind", "body", "content_type", "status"),
    [
        ("video", MP4, "text/plain", 415),  # what a cross-site form could send
        ("video", MP4, "application/x-www-form-urlencoded", 415),
        ("video", b"<html>not a video</html>", "video/mp4", 422),
        ("captions", b"1\n00:00 --> 00:01\nhi", "text/vtt", 422),
        ("video", b"", "video/mp4", 422),
        ("essay", MP4, "video/mp4", 422),
    ],
)
def test_bad_uploads_are_refused(
    client: TestClient,
    db: Session,
    media_dir: Path,
    kind: str,
    body: bytes,
    content_type: str,
    status: int,
) -> None:
    log_in(client, db, STAFF, staff=True)
    assert upload(client, kind, body, content_type).status_code == status
    assert not any(p.is_file() for p in media_dir.rglob("*"))


def test_an_oversized_upload_is_refused_and_not_kept(
    client: TestClient, db: Session, media_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(media.KINDS, "video", media.Kind("video/mp4", ".mp4", 32))
    log_in(client, db, STAFF, staff=True)
    assert upload(client, "video", MP4, "video/mp4").status_code in {413, 422}
    assert not any(p.is_file() for p in media_dir.rglob("*"))


# --- The editor --------------------------------------------------------------------------------


def test_create_then_students_see_it(client: TestClient, db: Session) -> None:
    log_in(client, db, STAFF, staff=True)
    paths = uploaded_paths(client)
    res = client.post("/api/staff/videos", json=video_body(paths, [checkpoint(45), checkpoint(20)]))
    assert res.status_code == 201, res.text
    made = res.json()
    assert [c["atSeconds"] for c in made["checkpoints"]] == [20, 45]
    assert made["checkpoints"][0]["question"]["correct"] == "a"  # staff see the answer

    student = client.get(f"/api/videos/{made['id']}")
    assert student.status_code == 200
    assert student.json()["mediaPath"] == paths[0]
    assert len(student.json()["checkpoints"]) == 2
    hints = db.scalars(select(Hint).order_by(Hint.activity_id, Hint.level)).all()
    assert len(hints) == 4
    listed = client.get("/api/staff/videos").json()
    assert listed == [
        {"id": made["id"], "title": "Meet BFS", "durationSeconds": 60, "checkpointCount": 2}
    ]


def test_a_video_must_point_at_uploaded_files(client: TestClient, db: Session) -> None:
    log_in(client, db, STAFF, staff=True)
    body = video_body(("/media/videos/missing.mp4", "/media/videos/missing.vtt"), [])
    res = client.post("/api/staff/videos", json=body)
    assert res.status_code == 422
    assert "Upload it again" in res.text


@pytest.mark.parametrize(
    "bad",
    [
        {"mediaPath": "/media/videos/../../etc/passwd.mp4"},
        {"mediaPath": "https://evil.example/x.mp4"},
        {"captionsPath": "/media/videos/x.mp4"},
        {"checkpoints": [checkpoint(99)]},  # after the end
        {"checkpoints": [checkpoint(5, question=None)]},
    ],
)
def test_invalid_videos_are_refused(client: TestClient, db: Session, bad: dict[str, Any]) -> None:
    log_in(client, db, STAFF, staff=True)
    body = {**video_body(uploaded_paths(client), []), **bad}
    assert client.post("/api/staff/videos", json=body).status_code == 422


def test_a_question_needs_a_valid_correct_option(client: TestClient, db: Session) -> None:
    log_in(client, db, STAFF, staff=True)
    bad = checkpoint(5)
    bad["question"]["correct"] = "z"
    res = client.post("/api/staff/videos", json=video_body(uploaded_paths(client), [bad]))
    assert res.status_code == 422
    assert "correct" in res.text


def test_editing_keeps_attempts_linked_and_removes_unused_checkpoints(
    client: TestClient, db: Session
) -> None:
    log_in(client, db, STAFF, staff=True)
    paths = uploaded_paths(client)
    made = client.post(
        "/api/staff/videos",
        json=video_body(paths, [checkpoint(10), checkpoint(20), checkpoint(30)]),
    ).json()
    answered, untouched, _dropped = made["checkpoints"]
    # A student answers the first; nobody touches the third.
    client.post(
        f"/api/activities/{answered['activityId']}/attempts",
        json={"submitted": {"selected": "a"}},
    )

    edited = [
        {**checkpoint(12, prompt="Reworded"), "id": answered["id"]},
        {**checkpoint(20), "id": untouched["id"]},
        checkpoint(40),  # new
    ]
    res = client.put(f"/api/staff/videos/{made['id']}", json=video_body(paths, edited))
    assert res.status_code == 200, res.text
    after = res.json()["checkpoints"]
    assert [c["atSeconds"] for c in after] == [12, 20, 40]
    assert after[0]["activityId"] == answered["activityId"]  # same activity: attempt still linked
    assert after[0]["question"]["prompt"] == "Reworded"
    # The dropped checkpoint's activity was unused, so it went with its hints: every activity
    # left belongs to a checkpoint. (Compared by set: SQLite may reuse the freed id.)
    db.expire_all()
    activity_ids = set(db.scalars(select(Activity.id)))
    assert activity_ids == {c["activityId"] for c in after}
    assert {h.activity_id for h in db.scalars(select(Hint))} == activity_ids

    # Dropping the answered checkpoint keeps its activity for the evaluation data.
    client.put(f"/api/staff/videos/{made['id']}", json=video_body(paths, after[1:]))
    db.expire_all()
    assert db.get(Activity, answered["activityId"]) is not None
    assert len(db.scalars(select(Attempt)).all()) == 1


def test_editing_with_a_checkpoint_from_another_video_is_refused(
    client: TestClient, db: Session
) -> None:
    log_in(client, db, STAFF, staff=True)
    paths = uploaded_paths(client)
    one = client.post("/api/staff/videos", json=video_body(paths, [checkpoint(10)])).json()
    two = client.post("/api/staff/videos", json=video_body(paths, [])).json()
    stolen = {**checkpoint(10), "id": one["checkpoints"][0]["id"]}
    res = client.put(f"/api/staff/videos/{two['id']}", json=video_body(paths, [stolen]))
    assert res.status_code == 422
    assert len(client.get(f"/api/staff/videos/{one['id']}").json()["checkpoints"]) == 1


def test_missing_video_is_404_for_staff(client: TestClient, db: Session) -> None:
    log_in(client, db, STAFF, staff=True)
    assert client.get("/api/staff/videos/999").status_code == 404
    body = video_body(uploaded_paths(client), [])
    assert client.put("/api/staff/videos/999", json=body).status_code == 404
