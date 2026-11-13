"""Restarting a module to redo its questions (POST /api/modules/{id}/restart, app/services/restart.py).

A restarted module opens at its start and shows every question unanswered, with its hints from
level 1 again. Nothing is taken away: it stays complete, the modules after it stay open, points and
badges stay, and every earlier answer and hint stays in the evaluation data.
"""

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Attempt, HintView, PointsEntry
from app.seed import load

PASSWORD = "Correct horse 1"  # noqa: S105 (a test account)


def mc(aid: int, module: int, purpose: str, hints: int = 4) -> dict[str, Any]:
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
        "solution": {"correct": "a", "feedback": {"b": "Not quite: B is wrong."}},
        "hints": [{"level": n, "body": f"h{n}"} for n in range(1, hints + 1)],
    }


COURSE: dict[str, Any] = {
    "objectives": [
        {"id": 1, "text": "One", "bloom_level": "b", "criterion": "Right.", "pass_fraction": 1.0}
    ],
    "modules": [
        {
            "id": 0,
            "slug": "m0",
            "title": "M0",
            "goals": ["g"],
            "estimated_minutes": 5,
            "segments": [
                {"id": 1, "kind": "text", "title": "Read", "body": "Text."},
                {"id": 2, "kind": "activity", "title": "Try", "activity_id": 101},
            ],
        },
        {
            "id": 1,
            "slug": "m1",
            "title": "M1",
            "goals": ["g"],
            "estimated_minutes": 5,
            "segments": [{"id": 3, "kind": "text", "title": "More", "body": "Text."}],
        },
        {
            "id": 6,
            "slug": "m6",
            "title": "M6",
            "goals": ["g"],
            "estimated_minutes": 5,
            "segments": [{"id": 4, "kind": "activity", "title": "Check", "activity_id": 601}],
        },
    ],
    "activities": [
        mc(101, 0, "practice"),
        mc(601, 6, "mastery", hints=2),
        {**mc(1101, 0, "review"), "module_id": None},
        {**mc(1102, 0, "mastery", hints=2), "module_id": None},
    ],
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


def setup(client: TestClient, db: Session, tmp_path: Path) -> None:
    (tmp_path / "course.json").write_text(json.dumps(COURSE), encoding="utf-8")
    load(db, tmp_path)
    body = {"email": "ada@example.com", "password": PASSWORD, "displayName": "Ada"}
    assert client.post("/api/auth/register", json=body).status_code == 201


def finish_module_0(client: TestClient) -> None:
    """Hint 1, a wrong answer, the right answer, then through to the end."""
    assert client.post("/api/activities/101/hints").status_code == 201
    client.post("/api/activities/101/attempts", json={"submitted": {"selected": "b"}})
    client.post("/api/activities/101/attempts", json={"submitted": {"selected": "a"}})
    assert client.post("/api/modules/0/position", json={"segmentPosition": 1}).status_code == 200
    detail = client.post("/api/modules/0/position", json={"segmentPosition": 1}).json()
    assert detail["status"] == "complete"


def points(db: Session) -> int:
    return db.scalar(select(func.coalesce(func.sum(PointsEntry.points), 0))) or 0


def test_a_restarted_module_shows_its_questions_afresh(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    setup(client, db, tmp_path)
    finish_module_0(client)
    earned = points(db)
    before = client.get("/api/activities/101").json()
    assert before["solved"] is True
    assert before["lastAttempt"]["submitted"] == {"selected": "a"}

    detail = client.post("/api/modules/0/restart").json()
    assert detail["restarted"] is True
    assert detail["status"] == "complete"  # the module after it stays open
    assert detail["currentSegmentPosition"] == 0
    activity = next(s for s in detail["segments"] if s["activityId"] == 101)
    assert (activity["done"], activity["attempted"]) == (False, False)

    after = client.get("/api/activities/101").json()
    assert after["solved"] is False
    assert after["lastAttempt"] is None  # the earlier answer isn't shown
    assert client.get("/api/activities/101/hints").json() == []
    assert client.post("/api/activities/101/hints").json()["level"] == 1  # the ladder starts again

    # Answered again: right, done again, and no points twice (FR-9.2).
    client.post("/api/activities/101/attempts", json={"submitted": {"selected": "a"}})
    assert client.get("/api/activities/101").json()["solved"] is True
    assert points(db) == earned
    assert client.get("/api/modules/1").status_code == 200  # still open

    # Nothing is deleted: every answer and hint stays in the evaluation data.
    assert db.scalar(select(func.count()).select_from(Attempt)) == 3
    assert db.scalar(select(func.count()).select_from(HintView)) == 2


def test_an_answer_after_a_restart_records_the_hints_of_this_round(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    setup(client, db, tmp_path)
    finish_module_0(client)  # used hint 1 in the first round
    client.post("/api/modules/0/restart")
    client.post("/api/activities/101/attempts", json={"submitted": {"selected": "a"}})
    last = db.scalars(select(Attempt).order_by(Attempt.id.desc())).first()
    assert last is not None
    assert last.hint_level == 0  # no hint this time round


def test_the_mastery_check_and_a_module_not_started_cant_be_restarted(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    setup(client, db, tmp_path)
    assert client.post("/api/modules/0/restart").status_code == 409  # not started yet
    finish_module_0(client)
    assert client.get("/api/modules/0").json()["canRestart"] is True
    assert client.post("/api/modules/6/restart").status_code in (403, 409)
    assert client.post("/api/modules/99/restart").status_code == 404
    client.cookies.clear()
    assert client.post("/api/modules/0/restart").status_code == 401
