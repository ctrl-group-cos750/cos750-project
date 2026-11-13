"""Restarting a module to redo its questions (POST /api/modules/{id}/restart, app/services/restart.py).

A restarted module opens at its start and shows every question unanswered, with its hints from
level 1 again. Nothing is taken away: it stays complete, the modules after it stay open, points and
badges stay, and every earlier answer and hint stays in the evaluation data.
"""

import copy
import csv
import io
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Activity,
    Attempt,
    Checkpoint,
    Event,
    HintView,
    Module,
    ModuleProgress,
    PointsEntry,
    User,
    UserBadge,
    Video,
)
from app.seed import load
from app.services.rewards import real_work

PASSWORD = "Correct horse 1"  # noqa: S105 (a test account)
STUDENT_BODY = {"email": "ada@example.com", "password": PASSWORD, "displayName": "Ada"}


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
    # Started but not finished: restarting would lose the student's place (13 Nov audit).
    assert client.post("/api/modules/0/position", json={"segmentPosition": 0}).status_code == 200
    assert client.get("/api/modules/0").json()["status"] == "in_progress"
    assert client.get("/api/modules/0").json()["canRestart"] is False
    assert client.post("/api/modules/0/restart").status_code == 409
    finish_module_0(client)
    assert client.get("/api/modules/0").json()["canRestart"] is True
    # Module 1 finished too, so the mastery check is open: refused for being the check.
    assert client.post("/api/modules/1/position", json={"segmentPosition": 0}).status_code == 200
    assert client.post("/api/modules/1/position", json={"segmentPosition": 0}).status_code == 200
    assert client.get("/api/modules/6").status_code == 200
    assert client.post("/api/modules/6/restart").status_code == 409
    assert client.post("/api/modules/99/restart").status_code == 404
    client.cookies.clear()
    assert client.post("/api/modules/0/restart").status_code == 401


def test_an_answer_given_away_before_a_restart_earns_no_more_after_it(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    """Every hint opened and a wrong answer, then a restart and the answer the hints gave: that
    is supported work after a wrong first answer: no points (FR-9.1) and no module reward (13 Nov
    audit; FR-9.6)."""
    setup(client, db, tmp_path)
    for _ in range(4):
        assert client.post("/api/activities/101/hints").status_code == 201
    client.post("/api/activities/101/attempts", json={"submitted": {"selected": "b"}})
    assert client.post("/api/modules/0/position", json={"segmentPosition": 1}).status_code == 200
    detail = client.post("/api/modules/0/position", json={"segmentPosition": 1}).json()
    assert detail["status"] == "complete"
    assert points(db) == 0
    assert client.post("/api/modules/0/restart").status_code == 200
    client.post("/api/activities/101/attempts", json={"submitted": {"selected": "a"}})
    # Nothing: right only after a wrong first attempt (FR-9.1), and no module points.
    assert points(db) == 0
    assert db.scalar(select(func.count()).select_from(UserBadge)) == 0


def test_a_restarted_module_s_video_asks_its_checkpoints_again(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    """The player and the module page agree after a restart: the checkpoint shows unanswered, so
    the student answers it again rather than being sent back to a video that won't ask (#211)."""
    course = copy.deepcopy(COURSE)
    course["modules"][0]["segments"].append(
        {"id": 5, "kind": "video", "title": "Watch", "body": "Narration."}
    )
    (tmp_path / "course.json").write_text(json.dumps(course), encoding="utf-8")
    load(db, tmp_path)
    question = Activity(
        kind="multiple_choice",
        title="Checkpoint",
        visible=True,
        config={"prompt": "Q", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]},
        solution={"correct": "a"},
    )
    video = Video(
        segment_id=5,
        title="V",
        media_path="/m.mp4",
        captions_path="/m.vtt",
        transcript="T",
        duration_seconds=60,
    )
    db.add_all([question, video])
    db.flush()
    db.add(Checkpoint(video_id=video.id, at_seconds=10, activity_id=question.id))
    db.commit()
    body = {"email": "ada@example.com", "password": PASSWORD, "displayName": "Ada"}
    assert client.post("/api/auth/register", json=body).status_code == 201

    right = {"submitted": {"selected": "a"}}
    client.post("/api/activities/101/attempts", json=right)
    client.post(f"/api/activities/{question.id}/attempts", json=right)
    for position in (1, 2, 2):
        detail = client.post("/api/modules/0/position", json={"segmentPosition": position}).json()
    assert detail["status"] == "complete"
    passed = client.get(f"/api/videos/{video.id}").json()["checkpoints"][0]["passed"]
    assert passed is True

    detail = client.post("/api/modules/0/restart").json()
    segment = next(s for s in detail["segments"] if s["id"] == 5)
    assert segment["done"] is False
    passed = client.get(f"/api/videos/{video.id}").json()["checkpoints"][0]["passed"]
    assert passed is False  # asked again, as the module page expects

    client.post(f"/api/activities/{question.id}/attempts", json=right)
    assert client.get(f"/api/videos/{video.id}").json()["checkpoints"][0]["passed"] is True
    segment = next(s for s in client.get("/api/modules/0").json()["segments"] if s["id"] == 5)
    assert segment["done"] is True


def test_hints_opened_after_a_right_answer_take_nothing_from_it(
    client: TestClient, db: Session
) -> None:
    """Quest A solved without hints, its module restarted, every hint on A opened, then quest B
    solved: All Quests is earned, because A's answer came before those hints (#211 review)."""
    load(db)
    assert client.post("/api/auth/register", json=STUDENT_BODY).status_code == 201
    user_id = int(client.get("/api/auth/me").json()["id"])
    for m in db.scalars(select(Module).where(Module.position < 5)):
        db.add(ModuleProgress(user_id=user_id, module_id=m.id, status="complete"))
    db.commit()
    right = {"submitted": {"selected": "a"}}
    assert client.post("/api/activities/380/attempts", json=right).status_code == 201
    assert client.post("/api/modules/3/restart").status_code == 200
    for _ in range(4):
        assert client.post("/api/activities/380/hints").status_code == 201
    assert client.post("/api/activities/480/attempts", json=right).status_code == 201
    badges = {(b["badge"], b["ref"]) for b in client.get("/api/rewards").json()["badges"]}
    assert ("all-quests", "") in badges

    # The same rule wherever rewards are decided (reward_module and the seed's backfill use it):
    # the first answer to 380 is still real work; an answer to it now would not be.
    first = db.scalar(select(Attempt.id).where(Attempt.activity_id == 380))
    assert db.scalar(select(Attempt.id).where(Attempt.id == first, real_work())) == first
    assert client.post("/api/activities/380/attempts", json=right).status_code == 201
    latest = db.scalar(select(func.max(Attempt.id)).where(Attempt.activity_id == 380))
    assert db.scalar(select(Attempt.id).where(Attempt.id == latest, real_work())) is None


def test_the_evaluation_data_tells_the_rounds_apart(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    """The hints CSV has each view's round; each restart's event has its attempt boundary; and a
    student who opens hint 3 on a question they already solved, after a restart, is not counted
    as needing support for it (#211 review)."""
    setup(client, db, tmp_path)
    finish_module_0(client)  # hint 1, wrong, right
    client.post("/api/modules/0/restart")
    boundary = db.scalar(select(func.max(Attempt.id)))
    for _ in range(3):
        assert client.post("/api/activities/101/hints").status_code == 201
    client.post("/api/modules/0/restart")  # a second restart keeps the first's boundary too

    events = db.scalars(
        select(Event).where(Event.type == "module_restarted").order_by(Event.id)
    ).all()
    assert [e.payload for e in events] == [
        {"round": 1, "after_attempt": boundary},
        {"round": 2, "after_attempt": boundary},
    ]

    body = {"email": "grace@example.com", "password": PASSWORD, "displayName": "Grace"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    grace = db.scalar(select(User).where(User.email == "grace@example.com"))
    assert grace is not None
    grace.is_staff = True
    db.commit()

    hints = list(csv.DictReader(io.StringIO(client.get("/api/staff/export/hints.csv").text)))
    assert [(h["level"], h["round"]) for h in hints] == [
        ("1", "0"),
        ("1", "1"),
        ("2", "1"),
        ("3", "1"),
    ]
    assert {h["after_attempt"] for h in hints[1:]} == {str(boundary)}
    (activity,) = client.get("/api/staff/insights").json()["activities"]
    assert activity["studentsWithSupport"] == 0  # hint 3 came after the right answer


def wrong(client: TestClient, activity: int = 101) -> None:
    response = client.post(
        f"/api/activities/{activity}/attempts", json={"submitted": {"selected": "b"}}
    )
    assert response.status_code == 201


def segment(client: TestClient, activity: int = 101) -> dict[str, Any]:
    detail = client.get("/api/modules/0").json()
    return next(s for s in detail["segments"] if s["activityId"] == activity)


def map_count(client: TestClient, module: int = 0) -> int:
    modules = client.get("/api/modules").json()
    return int(next(m for m in modules if m["id"] == module)["lookAgainCount"])


def test_two_tries_to_move_on_count_only_since_the_restart(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    """Two wrong answers let a student move on (FR-2.7, #214), but only within one round: two
    before a restart and one after it are one try in the new round, so the question still holds
    them (FR-2.8). Counting every try would let the restarted module through on one answer."""
    setup(client, db, tmp_path)
    wrong(client)
    wrong(client)  # two tries: may move on, marked to look at again
    assert (segment(client)["done"], segment(client)["lookAgain"]) == (True, True)
    assert client.post("/api/modules/0/position", json={"segmentPosition": 1}).status_code == 200
    assert client.get("/api/modules/0").json()["status"] == "complete"

    client.post("/api/modules/0/restart")
    wrong(client)  # the first try of this round
    held = segment(client)
    assert (held["done"], held["attempted"], held["lookAgain"]) == (False, True, False)
    assert map_count(client) == 0  # the map counts this round too

    wrong(client)  # the second: may move on again, and marked again
    assert (segment(client)["done"], segment(client)["lookAgain"]) == (True, True)
    assert map_count(client) == 1


def test_look_again_counts_only_since_the_restart(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    """Right before a restart and wrong twice after it: this round has no right answer, so the
    question is marked to look at again, on the module page and on the map (FR-2.7, FR-2.8)."""
    setup(client, db, tmp_path)
    finish_module_0(client)  # wrong, then right
    assert (segment(client)["lookAgain"], map_count(client)) == (False, 0)

    client.post("/api/modules/0/restart")
    wrong(client)
    wrong(client)
    moved_on = segment(client)
    assert (moved_on["done"], moved_on["lookAgain"]) == (True, True)
    assert map_count(client) == 1


def test_a_module_only_tested_out_of_cant_be_restarted(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    """Testing out (FR-8.2) isn't working through: there is nothing to redo yet, so the restart is
    neither offered nor allowed, and `canRestart` agrees with the route. Worked through to its end
    it completes, and may be restarted then."""
    setup(client, db, tmp_path)
    user = db.scalar(select(User).where(User.email == "ada@example.com"))
    assert user is not None
    db.add(ModuleProgress(user_id=user.id, module_id=0, status="tested_out"))
    db.commit()
    module = client.get("/api/modules/0").json()
    assert (module["status"], module["canRestart"]) == ("tested_out", False)
    assert client.post("/api/modules/0/restart").status_code == 409

    finish_module_0(client)
    module = client.get("/api/modules/0").json()
    assert (module["status"], module["canRestart"]) == ("complete", True)
    assert client.post("/api/modules/0/restart").status_code == 200
