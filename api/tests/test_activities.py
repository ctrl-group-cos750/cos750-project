"""The code-activity endpoints end to end (HTTP + database): grading by comparison, the attempt
recorded, and the solution never leaving the server. No code is executed anywhere."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from support import open_module

from app.models import Activity, Attempt, Hint, HintView

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
    activity = Activity(**{"module_id": open_module(db), **data})
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


# --- Multiple choice and the hint ladder (FR-4.2, FR-4.4, FR-4.5) -----------------------------

CHOICE: dict[str, Any] = {
    "kind": "multiple_choice",
    "title": "Which leaves the queue?",
    "visible": True,
    "config": {
        "prompt": "Which leaves the queue?",
        "options": [{"id": "a", "label": "A"}, {"id": "c", "label": "C"}],
    },
    "solution": {"correct": "a", "feedback": {"c": "Taking the newest first is a stack."}},
}


def make_choice_with_hints(db: Session, levels: tuple[int, ...] = (1, 2, 3, 4)) -> int:
    activity_id = make_activity(db, **CHOICE)
    db.add_all(Hint(activity_id=activity_id, level=n, body=f"hint {n}") for n in levels)
    db.commit()
    return activity_id


def test_get_multiple_choice_hides_the_answer_and_its_feedback(
    client: TestClient, db: Session
) -> None:
    activity_id = make_activity(db, **CHOICE)
    log_in(client)
    res = client.get(f"/api/activities/{activity_id}")
    assert res.json()["config"]["prompt"] == "Which leaves the queue?"
    assert "correct" not in res.text
    assert "stack" not in res.text


def test_multiple_choice_attempt_gives_the_reason_a_wrong_answer_is_wrong(
    client: TestClient, db: Session
) -> None:
    activity_id = make_activity(db, **CHOICE)
    log_in(client)
    res = client.post(
        f"/api/activities/{activity_id}/attempts", json={"submitted": {"selected": "c"}}
    )
    assert res.status_code == 201
    assert res.json()["correct"] is False
    assert res.json()["feedback"] == "Taking the newest first is a stack."
    right = client.post(
        f"/api/activities/{activity_id}/attempts", json={"submitted": {"selected": "a"}}
    )
    assert right.json()["correct"] is True


def test_hints_come_one_level_at_a_time_and_then_run_out(client: TestClient, db: Session) -> None:
    activity_id = make_choice_with_hints(db)
    log_in(client)
    shown = [client.post(f"/api/activities/{activity_id}/hints").json() for _ in range(4)]
    assert [h["level"] for h in shown] == [1, 2, 3, 4]
    assert [h["hasMore"] for h in shown] == [True, True, True, False]
    # Warn before level 3: the response to level 2 says the next one counts as support.
    assert [h["nextCountsAsSupport"] for h in shown] == [False, True, True, False]
    assert client.post(f"/api/activities/{activity_id}/hints").status_code == 409
    assert len(db.scalars(select(HintView)).all()) == 4


def test_hint_progress_is_per_student(client: TestClient, db: Session) -> None:
    activity_id = make_choice_with_hints(db)
    log_in(client)
    client.post(f"/api/activities/{activity_id}/hints")
    client.post("/api/auth/logout")
    other = {**STUDENT, "email": "grace@example.com"}
    assert client.post("/api/auth/register", json=other).status_code == 201
    assert client.post(f"/api/activities/{activity_id}/hints").json()["level"] == 1


def test_an_activity_without_hints_is_409(client: TestClient, db: Session) -> None:
    activity_id = make_activity(db, **CHOICE)
    log_in(client)
    assert client.post(f"/api/activities/{activity_id}/hints").status_code == 409


def test_hints_require_a_login_and_an_existing_activity(client: TestClient, db: Session) -> None:
    activity_id = make_choice_with_hints(db)
    assert client.post(f"/api/activities/{activity_id}/hints").status_code == 401
    log_in(client)
    assert client.post("/api/activities/999/hints").status_code == 404


def test_an_attempt_records_the_highest_hint_level_seen_before_it(
    client: TestClient, db: Session
) -> None:
    activity_id = make_choice_with_hints(db)
    log_in(client)
    url = f"/api/activities/{activity_id}/attempts"
    first = client.post(url, json={"submitted": {"selected": "c"}})
    assert first.json()["hintLevel"] == 0
    for _ in range(3):
        client.post(f"/api/activities/{activity_id}/hints")
    second = client.post(url, json={"submitted": {"selected": "a"}})
    assert second.json()["hintLevel"] == 3
    stored = db.scalars(select(Attempt).order_by(Attempt.id)).all()
    assert [a.hint_level for a in stored] == [0, 3]


def test_get_hints_returns_already_revealed_hints(client: TestClient, db: Session) -> None:
    activity_id = make_choice_with_hints(db)
    assert client.get(f"/api/activities/{activity_id}/hints").status_code == 401
    log_in(client)
    assert client.get("/api/activities/999/hints").status_code == 404

    # Initially empty
    empty = client.get(f"/api/activities/{activity_id}/hints")
    assert empty.status_code == 200
    assert empty.json() == []

    # Reveal hints 1 and 2
    client.post(f"/api/activities/{activity_id}/hints")
    client.post(f"/api/activities/{activity_id}/hints")

    revealed = client.get(f"/api/activities/{activity_id}/hints")
    assert revealed.status_code == 200
    hints = revealed.json()
    assert len(hints) == 2
    assert [h["level"] for h in hints] == [1, 2]
    assert [h["hasMore"] for h in hints] == [True, True]
    assert [h["nextCountsAsSupport"] for h in hints] == [False, True]


# --- Every correct order (FR-5.4, #145) -----------------------------------------------------------

# Lines 1 and 2 may swap; 0 comes first and 3 last. 9 is a distractor.
GROUPED: dict[str, Any] = {
    "kind": "parsons",
    "title": "Order the BFS set-up",
    "visible": True,
    "config": {"lines": [{"id": i, "text": f"line {i}"} for i in (0, 1, 2, 3, 9)]},
    "solution": {"order": [0, [1, 2], 3]},
}


def test_an_equivalent_order_passes_and_is_recorded_as_correct(
    client: TestClient, db: Session
) -> None:
    activity_id = make_activity(db, **GROUPED)
    log_in(client)
    for order in ([0, 1, 2, 3], [0, 2, 1, 3]):
        res = client.post(
            f"/api/activities/{activity_id}/attempts", json={"submitted": {"order": order}}
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert (body["correct"], body["score"], body["feedback"]) == (True, 1.0, "All correct.")
        assert [p["correct"] for p in body["parts"]] == [True] * 4
    stored = db.scalars(select(Attempt).where(Attempt.activity_id == activity_id)).all()
    assert [a.correct for a in stored] == [True, True]
    assert all(a.score == 1.0 for a in stored)
    # The parts the mastery rule counts are stored with the attempt (app/services/mastery.py).
    assert [p["correct"] for p in stored[1].detail["parts"]] == [True] * 4


def test_one_misplaced_line_is_the_only_line_marked_wrong(client: TestClient, db: Session) -> None:
    activity_id = make_activity(db, **GROUPED)
    log_in(client)
    res = client.post(
        f"/api/activities/{activity_id}/attempts", json={"submitted": {"order": [3, 0, 2, 1]}}
    )
    body = res.json()
    assert body["correct"] is False
    assert body["score"] == 0.75
    assert [p["correct"] for p in body["parts"]] == [False, True, True, True]
    assert body["parts"][0]["message"] == "This line is in the wrong place."
    assert "solution" not in res.text
    assert "[1, 2]" not in res.text


def test_hostile_parsons_submissions_are_refused_or_graded_wrong(
    client: TestClient, db: Session
) -> None:
    activity_id = make_activity(db, **GROUPED)
    log_in(client)
    url = f"/api/activities/{activity_id}/attempts"
    for bad in (
        {},
        {"order": "0123"},
        {"order": [[0, 1], 2, 3]},  # a group is solution notation, not an answer
        {"order": [0, None, 2, 3]},
        {"order": list(range(101))},
        {"order": [0, 1, 2, 3], "alternatives": [[3, 2, 1, 0]]},
        {"order": [-5, 2**62, 1, 3]},  # an id no Postgres integer can hold (#139)
    ):
        assert client.post(url, json={"submitted": bad}).status_code == 422, bad
    # Empty, or naming a line the problem doesn't have: not an answer (422, #139).
    for foreign in ([], [-5, 2**31 - 1, 1, 3]):
        assert client.post(url, json={"submitted": {"order": foreign}}).status_code == 422, foreign
    for wrong in ([0, 1, 2, 3, 9], [0, 0, 0, 0], [3, 2, 1, 0]):  # 9 is the distractor
        res = client.post(url, json={"submitted": {"order": wrong}})
        assert res.status_code == 201, wrong
        assert res.json()["correct"] is False, wrong


def test_a_solution_stored_with_a_string_id_still_grades_over_http(
    client: TestClient, db: Session
) -> None:
    activity_id = make_activity(db, **{**GROUPED, "solution": {"order": [0, ["1", "2"], "3"]}})
    log_in(client)
    res = client.post(
        f"/api/activities/{activity_id}/attempts", json={"submitted": {"order": [0, 2, 1, 3]}}
    )
    assert res.status_code == 201, res.text
    assert res.json()["correct"] is True
