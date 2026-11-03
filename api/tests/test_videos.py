"""GET /api/videos/{id}: what the narrated player needs, with checkpoints in order, their
activities without answers, and which ones this student has passed (FR-3)."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Activity, Checkpoint, Video

STUDENT = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}


def choice(title: str) -> dict[str, Any]:
    return {
        "kind": "multiple_choice",
        "title": title,
        "visible": True,
        "config": {
            "prompt": title,
            "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        },
        "solution": {"correct": "a", "feedback": {"b": "secret reason"}},
    }


def make_video(db: Session) -> tuple[int, int, int]:
    """A video with checkpoints added out of order (45 s first) to check the ordering."""
    late, early = Activity(**choice("late")), Activity(**choice("early"))
    video = Video(
        title="Meet BFS",
        media_path="/media/m3/meet-bfs.mp4",
        captions_path="/media/m3/meet-bfs.vtt",
        transcript="Words",
        duration_seconds=60,
    )
    db.add_all([late, early, video])
    db.flush()
    db.add_all(
        [
            Checkpoint(video_id=video.id, at_seconds=45, activity_id=late.id),
            Checkpoint(video_id=video.id, at_seconds=20, activity_id=early.id),
        ]
    )
    db.commit()
    return video.id, early.id, late.id


def test_video_has_paths_transcript_and_ordered_checkpoints(
    client: TestClient, db: Session
) -> None:
    video_id, early, late = make_video(db)
    assert client.post("/api/auth/register", json=STUDENT).status_code == 201
    res = client.get(f"/api/videos/{video_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["mediaPath"] == "/media/m3/meet-bfs.mp4"
    assert body["captionsPath"] == "/media/m3/meet-bfs.vtt"
    assert body["durationSeconds"] == 60
    assert [c["atSeconds"] for c in body["checkpoints"]] == [20, 45]
    assert [c["activity"]["id"] for c in body["checkpoints"]] == [early, late]
    assert [c["passed"] for c in body["checkpoints"]] == [False, False]


def test_video_never_contains_checkpoint_answers(client: TestClient, db: Session) -> None:
    video_id, _, _ = make_video(db)
    client.post("/api/auth/register", json=STUDENT)
    res = client.get(f"/api/videos/{video_id}")
    assert "solution" not in res.text
    assert "secret reason" not in res.text
    assert '"correct"' not in res.text


def test_a_checkpoint_is_passed_only_after_this_students_correct_answer(
    client: TestClient, db: Session
) -> None:
    video_id, early, _ = make_video(db)
    client.post("/api/auth/register", json=STUDENT)
    url = f"/api/activities/{early}/attempts"
    client.post(url, json={"submitted": {"selected": "b"}})
    assert [c["passed"] for c in client.get(f"/api/videos/{video_id}").json()["checkpoints"]] == [
        False,
        False,
    ]
    client.post(url, json={"submitted": {"selected": "a"}})
    assert [c["passed"] for c in client.get(f"/api/videos/{video_id}").json()["checkpoints"]] == [
        True,
        False,
    ]
    # Another student starts from scratch.
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={**STUDENT, "email": "grace@example.com"})
    assert [c["passed"] for c in client.get(f"/api/videos/{video_id}").json()["checkpoints"]] == [
        False,
        False,
    ]


def test_video_requires_a_login(client: TestClient, db: Session) -> None:
    video_id, _, _ = make_video(db)
    assert client.get(f"/api/videos/{video_id}").status_code == 401


def test_missing_video_is_404(client: TestClient, db: Session) -> None:
    client.post("/api/auth/register", json=STUDENT)
    assert client.get("/api/videos/999").status_code == 404
