"""The pilot's event log (FR-10.1): POST /api/events for what only the browser sees, and the
events the server logs itself (app/services/events.py)."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Activity,
    Checkpoint,
    Event,
    GraphScenario,
    Hint,
    Module,
    Segment,
    User,
    Video,
)
from app.seed import load
from app.services.events import CLIENT_EVENTS, EVENT_TYPES, SERVER_EVENTS, log_event

STUDENT = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}


def log_in(client: TestClient) -> int:
    assert client.post("/api/auth/register", json=STUDENT).status_code == 201
    return int(client.get("/api/auth/me").json()["id"])


def content(db: Session) -> dict[str, int]:
    """A video with one checkpoint, and a module with one text segment."""
    activity = Activity(
        kind="multiple_choice",
        title="Q",
        visible=True,
        config={"prompt": "Q", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]},
        solution={"correct": "a", "feedback": {}},
    )
    video = Video(
        title="Meet BFS",
        media_path="/media/v.mp4",
        captions_path="/media/v.vtt",
        transcript="Words",
        duration_seconds=60,
    )
    module = Module(id=3, slug="m3", title="M3", goals=["g"], estimated_minutes=5, position=3)
    db.add_all([activity, video, module])
    db.flush()
    checkpoint = Checkpoint(video_id=video.id, at_seconds=20, activity_id=activity.id)
    segment = Segment(module_id=3, position=1, kind="text", title="T", body="b")
    db.add_all(
        [
            checkpoint,
            segment,
            *[Hint(activity_id=activity.id, level=n, body=f"h{n}") for n in (1, 2)],
        ]
    )
    db.commit()
    return {
        "video": video.id,
        "checkpoint": checkpoint.id,
        "segment": segment.id,
        "activity": activity.id,
    }


def events_of(db: Session, user_id: int) -> list[tuple[str, str, dict[str, Any]]]:
    db.expire_all()
    return [
        (e.type, e.ref, e.payload)
        for e in db.scalars(select(Event).where(Event.user_id == user_id).order_by(Event.id))
    ]


def test_the_types_are_split_between_server_and_browser() -> None:
    assert {"hint_shown", "result_changed", "module_completed"} == SERVER_EVENTS
    assert {
        "video_started",
        "video_completed",
        "checkpoint_reached",
        "segment_viewed",
        "prediction_made",
    } == CLIENT_EVENTS
    assert EVENT_TYPES == SERVER_EVENTS | CLIENT_EVENTS


def test_reporting_needs_a_login(client: TestClient, db: Session) -> None:
    assert (
        client.post("/api/events", json={"type": "video_started", "targetId": 1}).status_code == 401
    )


def test_the_browser_reports_what_it_saw(client: TestClient, db: Session) -> None:
    ids = content(db)
    user = log_in(client)
    for type, target in (
        ("video_started", ids["video"]),
        ("checkpoint_reached", ids["checkpoint"]),
        ("video_completed", ids["video"]),
        ("segment_viewed", ids["segment"]),
    ):
        response = client.post("/api/events", json={"type": type, "targetId": target})
        assert response.status_code == 204
    assert events_of(db, user) == [
        ("video_started", f"video:{ids['video']}", {}),
        ("checkpoint_reached", f"checkpoint:{ids['checkpoint']}", {}),
        ("video_completed", f"video:{ids['video']}", {}),
        ("segment_viewed", f"segment:{ids['segment']}", {}),
    ]
    stored = db.scalars(select(Event)).first()
    assert stored is not None
    assert stored.created_at is not None


@pytest.mark.parametrize(
    "body",
    [
        {"type": "hint_shown", "targetId": 1},  # the server's to log, not the browser's
        {"type": "result_changed", "targetId": 1},
        {"type": "anything", "targetId": 1},
        {"type": "video_started", "targetId": 0},
        {"type": "video_started", "targetId": "1; DROP TABLE events"},
        {"type": "video_started"},
    ],
)
def test_the_browser_can_only_report_known_events(
    client: TestClient, db: Session, body: dict[str, Any]
) -> None:
    user = log_in(client)
    assert client.post("/api/events", json=body).status_code == 422
    assert events_of(db, user) == []


def test_an_event_about_something_that_does_not_exist_is_404(
    client: TestClient, db: Session
) -> None:
    content(db)
    user = log_in(client)
    for type in ("video_started", "checkpoint_reached", "segment_viewed", "prediction_made"):
        response = client.post("/api/events", json={"type": type, "targetId": 9999})
        assert response.status_code == 404
    assert events_of(db, user) == []


def test_a_prediction_in_the_visualiser_is_logged_with_whether_it_was_right(
    client: TestClient, db: Session
) -> None:
    """Prediction mode (FR-6.4) is recorded: each prediction, about the graph (#146)."""
    graph = GraphScenario(
        name="Campus", vertices=["A", "B"], edges=[{"source": "A", "target": "B"}], start_vertex="A"
    )
    db.add(graph)
    db.commit()
    user = log_in(client)
    for correct in (True, False):
        body = {"type": "prediction_made", "targetId": graph.id, "correct": correct}
        assert client.post("/api/events", json=body).status_code == 204
    # `correct` is kept only for a prediction.
    video = content(db)["video"]
    body = {"type": "video_started", "targetId": video, "correct": True}
    assert client.post("/api/events", json=body).status_code == 204
    assert events_of(db, user) == [
        ("prediction_made", f"graph:{graph.id}", {"correct": True}),
        ("prediction_made", f"graph:{graph.id}", {"correct": False}),
        ("video_started", f"video:{video}", {}),
    ]


def test_a_runaway_loop_is_stopped(client: TestClient, db: Session) -> None:
    ids = content(db)
    log_in(client)
    body = {"type": "video_started", "targetId": ids["video"]}
    codes = [client.post("/api/events", json=body).status_code for _ in range(121)]
    assert codes[:120] == [204] * 120
    assert codes[120] == 429


def test_showing_a_hint_is_logged_with_its_level(client: TestClient, db: Session) -> None:
    ids = content(db)
    user = log_in(client)
    for _ in range(2):
        assert client.post(f"/api/activities/{ids['activity']}/hints").status_code == 201
    assert events_of(db, user) == [
        ("hint_shown", f"activity:{ids['activity']}", {"level": 1}),
        ("hint_shown", f"activity:{ids['activity']}", {"level": 2}),
    ]


def test_the_server_refuses_an_unknown_event_type(db: Session) -> None:
    student = User(email="s@example.com", display_name="S", password_hash="x")  # noqa: S106
    db.add(student)
    db.flush()
    with pytest.raises(ValueError, match="No event type"):
        log_event(db, student.id, "made_up", "x:1")


def mcq(aid: int, module: int | None, purpose: str) -> dict[str, Any]:
    hints = [{"level": n, "body": f"h{n}"} for n in (1, 2, 3, 4)] if purpose == "review" else []
    return {
        "id": aid,
        "kind": "multiple_choice",
        "title": f"Q{aid}",
        "module_id": module,
        "objective_id": 1,
        "purpose": purpose,
        "config": {
            "prompt": "Q",
            "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        },
        "solution": {"correct": "a"},
        "hints": hints,
    }


COURSE: dict[str, Any] = {
    "objectives": [
        {"id": 1, "text": "One", "bloom_level": "b", "criterion": "R.", "pass_fraction": 1.0}
    ],
    "modules": [{"id": 6, "slug": "m6", "title": "M6", "goals": ["g"], "estimated_minutes": 5}],
    "activities": [mcq(601, 6, "mastery"), mcq(1101, None, "review"), mcq(1102, None, "mastery")],
    "review_paths": [
        {
            "objective_id": 1,
            "segments": [
                {"id": 1100, "kind": "worked_example", "title": "Again", "body": "Like this."},
                {"id": 1101, "kind": "activity", "title": "Practice", "activity_id": 1101},
                {"id": 1102, "kind": "activity", "title": "Fresh", "activity_id": 1102},
            ],
        }
    ],
}


def test_a_result_changing_is_logged_with_where_it_came_from(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    (tmp_path / "course.json").write_text(json.dumps(COURSE), encoding="utf-8")
    load(db, tmp_path)
    user = log_in(client)
    body = {"submitted": {"selected": "b"}}
    assert client.post("/api/activities/601/attempts", json=body).status_code == 201
    body = {"submitted": {"selected": "a"}}
    # A mastery check item takes one answer (#144).
    assert client.post("/api/activities/601/attempts", json=body).status_code == 409
    assert client.post("/api/activities/1102/attempts", json=body).status_code == 201
    assert events_of(db, user) == [
        (
            "result_changed",
            "objective:1",
            {"from": "not_attempted", "to": "not_yet", "viaReview": False},
        ),
        (
            "result_changed",
            "objective:1",
            {"from": "not_yet", "to": "met_independently", "viaReview": True},
        ),
    ]
