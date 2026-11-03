"""The code-activity endpoints end to end (HTTP + database): grading by comparison, the attempt
recorded, and the solution never leaving the server. No code is executed anywhere."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt

STUDENT = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}

PARSONS: dict[str, Any] = {
    "kind": "parsons",
    "title": "Order the BFS loop",
    "visible": True,
    "config": {"lines": [{"id": 0, "text": "a"}, {"id": 1, "text": "b"}, {"id": 2, "text": "c"}]},
    "solution": {"order": [0, 1, 2]},
}
FILL_IN: dict[str, Any] = {
    "kind": "fill_in",
    "title": "Complete add_edge",
    "visible": False,
    "config": {"code": "x = __1__", "blanks": [1], "options": ["start", "end"]},
    "solution": {"answers": {1: "start"}},
}


def make_activity(db: Session, **data: Any) -> int:
    activity = Activity(**data)
    db.add(activity)
    db.commit()
    return activity.id


def log_in(client: TestClient) -> None:
    assert client.post("/api/auth/register", json=STUDENT).status_code == 201


def test_get_activity_returns_the_config_but_never_the_solution(
    client: TestClient, db: Session
) -> None:
    activity_id = make_activity(db, **PARSONS)
    log_in(client)
    res = client.get(f"/api/activities/{activity_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "parsons"
    assert len(body["config"]["lines"]) == 3
    assert "solution" not in body
    assert '"order"' not in res.text  # the correct order is the solution; it must not leak


def test_get_activity_requires_a_login(client: TestClient, db: Session) -> None:
    activity_id = make_activity(db, **PARSONS)
    assert client.get(f"/api/activities/{activity_id}").status_code == 401


def test_get_missing_activity_is_404(client: TestClient, db: Session) -> None:
    log_in(client)
    assert client.get("/api/activities/999").status_code == 404


def test_correct_parsons_submission_passes_and_is_recorded(client: TestClient, db: Session) -> None:
    activity_id = make_activity(db, **PARSONS)
    log_in(client)
    res = client.post(
        f"/api/activities/{activity_id}/attempts", json={"submitted": {"order": [0, 1, 2]}}
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["correct"] is True
    assert body["score"] == 1.0
    assert body["activityId"] == activity_id
    stored = db.scalars(select(Attempt).where(Attempt.activity_id == activity_id)).all()
    assert len(stored) == 1
    assert stored[0].correct is True


def test_wrong_parsons_submission_fails_without_leaking_the_solution(
    client: TestClient, db: Session
) -> None:
    activity_id = make_activity(db, **PARSONS)
    log_in(client)
    res = client.post(
        f"/api/activities/{activity_id}/attempts", json={"submitted": {"order": [1, 0, 2]}}
    )
    assert res.status_code == 201
    body = res.json()
    assert body["correct"] is False
    assert body["score"] < 1.0
    assert len(body["parts"]) == 3
    assert "solution" not in res.text
    assert '"order"' not in res.text  # neither the submitted nor the solution order is echoed back


def test_hidden_fill_in_is_graded_by_token(client: TestClient, db: Session) -> None:
    activity_id = make_activity(db, **FILL_IN)
    log_in(client)
    right = client.post(
        f"/api/activities/{activity_id}/attempts", json={"submitted": {"answers": {"1": "start"}}}
    )
    assert right.json()["correct"] is True
    wrong = client.post(
        f"/api/activities/{activity_id}/attempts", json={"submitted": {"answers": {"1": "end"}}}
    )
    assert wrong.json()["correct"] is False


def test_submitting_requires_a_login(client: TestClient, db: Session) -> None:
    activity_id = make_activity(db, **PARSONS)
    res = client.post(
        f"/api/activities/{activity_id}/attempts", json={"submitted": {"order": [0, 1, 2]}}
    )
    assert res.status_code == 401


def test_submitting_to_a_missing_activity_is_404(client: TestClient, db: Session) -> None:
    log_in(client)
    res = client.post("/api/activities/999/attempts", json={"submitted": {"order": [0]}})
    assert res.status_code == 404


def test_a_malformed_submission_is_rejected_422(client: TestClient, db: Session) -> None:
    activity_id = make_activity(db, **PARSONS)
    log_in(client)
    res = client.post(f"/api/activities/{activity_id}/attempts", json={"submitted": {"nope": 1}})
    assert res.status_code == 422


def test_attempts_are_append_only(client: TestClient, db: Session) -> None:
    activity_id = make_activity(db, **PARSONS)
    log_in(client)
    for order in ([1, 0, 2], [0, 1, 2]):
        client.post(f"/api/activities/{activity_id}/attempts", json={"submitted": {"order": order}})
    stored = db.scalars(select(Attempt).where(Attempt.activity_id == activity_id)).all()
    assert len(stored) == 2
