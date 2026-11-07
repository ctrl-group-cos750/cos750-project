"""The mastery check and report (FR-7.1 to FR-7.4, FR-7.6): the rules in app/services/mastery.py,
the stored results and what they earn, and GET /api/me/report."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, HintView, ObjectiveResult, User
from app.schemas.graphs import GraphScenarioOut
from app.seed import ObjectiveFixture, load, read_fixtures
from app.services import mastery, rewards
from app.services.bfs import run_bfs
from app.services.mastery import Answer, Rule, decide

STUDENT = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}
RIGHT = {"submitted": {"selected": "a"}}
WRONG = {"submitted": {"selected": "b"}}


def ans(*parts: bool, hint: int = 0, attempt: int = 1) -> Answer:
    return Answer(attempt, parts, hint)


# --- The rule (ID document Table 1) -------------------------------------------------------------


@pytest.mark.parametrize(
    ("rule", "right", "total", "met"),
    [
        (Rule(pass_fraction=0.8), 4, 5, True),  # "at least 4 of 5"
        (Rule(pass_fraction=0.8), 3, 5, False),
        (Rule(pass_fraction=0.75), 3, 4, True),  # "at least 3 of 4"
        (Rule(pass_fraction=0.75), 2, 4, False),
        (Rule(pass_fraction=0.8), 8, 10, True),  # "at least 80%"
        (Rule(pass_fraction=0.8), 7, 10, False),
        (Rule(pass_fraction=1.0), 12, 12, True),  # "matches the reference solution"
        (Rule(pass_fraction=1.0), 11, 12, False),
        (Rule(max_wrong=1), 6, 7, True),  # "with at most one error"
        (Rule(max_wrong=1), 5, 7, False),
        (Rule(max_wrong=1), 7, 7, True),
    ],
)
def test_a_rule_counts_parts(rule: Rule, right: int, total: int, met: bool) -> None:
    assert rule.met(right, total) is met


def test_every_committed_objective_has_exactly_one_rule() -> None:
    for o in read_fixtures().objectives:
        assert (o.pass_fraction is None) != (o.max_wrong is None), o.id


@pytest.mark.parametrize("rule", [{}, {"pass_fraction": 0.8, "max_wrong": 1}])
def test_an_objective_needs_exactly_one_rule(rule: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="pass_fraction or max_wrong"):
        ObjectiveFixture(id=1, text="t", bloom_level="b", criterion="c", **rule)


# --- Deciding a result (FR-7.2) ------------------------------------------------------------------


FOUR_OF_FIVE = Rule(pass_fraction=0.8)


def test_nothing_answered_is_not_attempted() -> None:
    assert decide(FOUR_OF_FIVE, [None, None]) == "not_attempted"


def test_an_objective_without_items_is_not_attempted() -> None:
    assert decide(FOUR_OF_FIVE, []) == "not_attempted"


def test_it_stays_not_attempted_until_every_item_is_answered() -> None:
    assert decide(FOUR_OF_FIVE, [ans(True), None]) == "not_attempted"


def test_met_without_hint_3_or_4_is_independent() -> None:
    answers = [ans(True, hint=2), ans(True), ans(True), ans(True), ans(False)]
    assert decide(FOUR_OF_FIVE, answers) == "met_independently"


def test_needing_an_answer_given_after_hint_3_or_4_is_with_support() -> None:
    answers = [ans(True, hint=3), ans(True), ans(True), ans(True), ans(False)]
    assert decide(FOUR_OF_FIVE, answers) == "met_with_support"


def test_the_worked_solution_on_an_item_that_was_not_needed_is_still_independent() -> None:
    answers = [ans(True, hint=4), ans(True), ans(True), ans(True), ans(True)]
    assert decide(FOUR_OF_FIVE, answers) == "met_independently"


def test_not_meeting_the_rule_even_with_support_is_not_yet() -> None:
    answers = [ans(True, hint=4), ans(True), ans(True), ans(False), ans(False)]
    assert decide(FOUR_OF_FIVE, answers) == "not_yet"


def test_parts_of_one_item_count_one_by_one() -> None:
    trace = Rule(max_wrong=1)
    assert decide(trace, [ans(True, True, False, True)]) == "met_independently"
    assert decide(trace, [ans(True, False, False, True)]) == "not_yet"
    assert decide(trace, [ans(True, True, False, True, hint=3)]) == "met_with_support"


# --- Through the API, on a small course ----------------------------------------------------------


def mcq(id: int, objective: int, purpose: str = "mastery", module: int = 6) -> dict[str, Any]:
    return {
        "id": id,
        "kind": "multiple_choice",
        "title": f"Question {id}",
        "module_id": module,
        "objective_id": objective,
        "purpose": purpose,
        "config": {
            "prompt": "Q",
            "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        },
        "solution": {"correct": "a"},
    }


def small_course(rule_1: dict[str, Any] | None = None) -> dict[str, Any]:
    """Objective 1 needs 2 of 2 MCQs (601, 602), objective 2 one MCQ (603); 301 is practice."""
    return {
        "objectives": [
            {"id": 1, "text": "One", "bloom_level": "b", "criterion": "Both right."}
            | (rule_1 or {"pass_fraction": 1.0}),
            {"id": 2, "text": "Two", "bloom_level": "b", "criterion": "Right.", "max_wrong": 0},
        ],
        "modules": [
            {"id": n, "slug": f"m{n}", "title": f"M{n}", "goals": ["g"], "estimated_minutes": 5}
            for n in (3, 6)
        ],
        "activities": [
            mcq(301, 1, purpose="practice", module=3),
            mcq(601, 1),
            mcq(602, 1),
            mcq(603, 2),
        ],
    }


@pytest.fixture
def course(tmp_path: Path, db: Session) -> Path:
    (tmp_path / "course.json").write_text(json.dumps(small_course()), encoding="utf-8")
    load(db, tmp_path)
    return tmp_path


def log_in(client: TestClient) -> int:
    assert client.post("/api/auth/register", json=STUDENT).status_code == 201
    return int(client.get("/api/auth/me").json()["id"])


def answer(client: TestClient, activity: int, body: dict[str, Any] = RIGHT) -> None:
    assert client.post(f"/api/activities/{activity}/attempts", json=body).status_code == 201


def states(client: TestClient) -> dict[int, str]:
    return {o["id"]: o["state"] for o in client.get("/api/me/report").json()["objectives"]}


def test_the_report_needs_a_login(client: TestClient, db: Session) -> None:
    assert client.get("/api/me/report").status_code == 401


def test_a_new_student_has_attempted_nothing_and_is_not_ready(
    client: TestClient, course: Path
) -> None:
    log_in(client)
    report = client.get("/api/me/report").json()
    assert report["ready"] is False
    assert report["objectives"][0] == {
        "id": 1,
        "text": "One",
        "criterion": "Both right.",
        "state": "not_attempted",
        "answered": 0,
        "total": 2,
    }


def test_answering_every_item_makes_the_student_ready(client: TestClient, course: Path) -> None:
    log_in(client)
    for item in (601, 602):
        answer(client, item)
    assert states(client) == {1: "met_independently", 2: "not_attempted"}
    answer(client, 603)
    report = client.get("/api/me/report").json()
    assert report["ready"] is True
    assert states(client) == {1: "met_independently", 2: "met_independently"}


def test_only_the_first_attempt_at_an_item_counts(client: TestClient, course: Path) -> None:
    log_in(client)
    answer(client, 603, WRONG)
    answer(client, 603, RIGHT)
    assert states(client)[2] == "not_yet"


def test_practice_items_do_not_count(client: TestClient, course: Path, db: Session) -> None:
    user = log_in(client)
    answer(client, 301)
    assert states(client)[1] == "not_attempted"
    assert db.scalars(select(ObjectiveResult).where(ObjectiveResult.user_id == user)).all() == []


def test_hint_3_before_an_answer_makes_it_met_with_support(
    client: TestClient, course: Path, db: Session
) -> None:
    user = log_in(client)
    db.add(HintView(user_id=user, activity_id=603, level=3))
    db.commit()
    answer(client, 603)
    assert states(client)[2] == "met_with_support"


def test_one_not_yet_means_not_ready(client: TestClient, course: Path) -> None:
    log_in(client)
    answer(client, 601)
    answer(client, 602)
    answer(client, 603, WRONG)
    report = client.get("/api/me/report").json()
    assert report["ready"] is False
    assert states(client) == {1: "met_independently", 2: "not_yet"}


def test_results_are_stored_with_their_evidence(
    client: TestClient, course: Path, db: Session
) -> None:
    user = log_in(client)
    answer(client, 601)
    answer(client, 602, WRONG)
    answer(client, 602)  # not evidence: only the first attempt counts
    rows = {
        r.objective_id: r
        for r in db.scalars(select(ObjectiveResult).where(ObjectiveResult.user_id == user))
    }
    assert rows[1].state == "not_yet"
    assert len(rows[1].evidence) == 2
    assert rows[2].state == "not_attempted"
    assert rows[2].evidence == []


def test_meeting_objectives_earns_badges_and_ready_for_the_lecture(
    client: TestClient, course: Path, db: Session
) -> None:
    user = log_in(client)
    db.add(HintView(user_id=user, activity_id=603, level=4))
    db.commit()
    for item in (601, 602, 603):
        answer(client, item)
    held = {(b.badge, b.tier) for b in rewards.badges_of(db, user)}
    # The course has objectives 1 and 2, so those are the ones Ready for the Lecture needs.
    assert held == {("lo1", "gold"), ("lo2", "bronze"), (rewards.READY_FOR_LECTURE, None)}
    # 601 and 602 alone, 603 after the worked solution; objective 1 alone, objective 2 with support.
    assert rewards.total_points(db, user) == 10 + 10 + 4 + 30 + 15


def test_a_rule_change_is_applied_on_the_next_seed_and_keeps_badges(
    client: TestClient, course: Path, db: Session
) -> None:
    user = log_in(client)
    answer(client, 601)
    answer(client, 602, WRONG)
    assert states(client)[1] == "not_yet"

    # Loosen objective 1 to "at least half right": the reseed recomputes everyone (FR-7.6).
    (course / "course.json").write_text(
        json.dumps(small_course({"pass_fraction": 0.5})), encoding="utf-8"
    )
    load(db, course)
    db.expire_all()
    stored = db.scalar(
        select(ObjectiveResult).where(
            ObjectiveResult.user_id == user, ObjectiveResult.objective_id == 1
        )
    )
    assert stored is not None
    assert stored.state == "met_independently"
    assert states(client)[1] == "met_independently"
    assert ("lo1", "gold") in {(b.badge, b.tier) for b in rewards.badges_of(db, user)}

    # Tighten it again: the result goes back to not yet, but the badge, once earned, stays.
    (course / "course.json").write_text(json.dumps(small_course()), encoding="utf-8")
    load(db, course)
    db.expire_all()
    assert states(client)[1] == "not_yet"
    assert ("lo1", "gold") in {(b.badge, b.tier) for b in rewards.badges_of(db, user)}


def test_recompute_all_skips_students_who_never_answered_a_mastery_item(
    course: Path, db: Session
) -> None:
    db.add(User(email="x@example.com", display_name="X", password_hash="x"))  # noqa: S106
    db.flush()
    assert mastery.recompute_all(db) == 0


def test_an_attempt_without_graded_parts_counts_as_one_part(course: Path, db: Session) -> None:
    from app.models import Attempt

    student = User(email="y@example.com", display_name="Y", password_hash="x")  # noqa: S106
    db.add(student)
    db.flush()
    db.add(
        Attempt(
            user_id=student.id,
            activity_id=603,
            submitted={},
            correct=True,
            score=1.0,
            detail={},
            hint_level=0,
        )
    )
    db.flush()
    outcomes = {o.objective.id: o.state for o in mastery.evaluate(db, student.id)}
    assert outcomes[2] == "met_independently"


# --- The committed course: module 6 covers every objective (FR-7.1) ------------------------------


def correct_submission(activity: Activity) -> dict[str, Any]:
    """The right answer to any committed item, built from its solution (or, for a trace, the BFS
    engine), so this test keeps working as the placeholders are replaced."""
    config, solution = activity.config, activity.solution
    match activity.kind:
        case "multiple_choice":
            return {"selected": solution["correct"]}
        case "matching":
            return {"pairs": solution["pairs"]}
        case "parsons" | "fix_the_bug":
            return {"order": solution["order"]}
        case "fill_in":
            return {"answers": solution["answers"]}
        case "choose_tests":
            return {"selected": solution["exposing"]}
        case "trace":
            steps = run_bfs(GraphScenarioOut(id=0, name="", **config)).steps
            return {
                "rows": [
                    {
                        "visitedVertex": s.visited_vertex,
                        "queue": s.queue,
                        "visited": s.visited,
                        "order": s.order,
                    }
                    for s in steps
                ]
            }
    raise AssertionError(f"no submission for {activity.kind}")


def test_module_6_has_mastery_items_for_every_objective() -> None:
    content = read_fixtures()
    covered = {a.objective_id for a in content.activities if a.module_id == 6}
    assert covered == {o.id for o in content.objectives}
    shown = {s.activity_id for m in content.modules if m.id == 6 for s in m.segments}
    assert {a.id for a in content.activities if a.module_id == 6} <= shown


def test_the_committed_mastery_check_can_be_passed(client: TestClient, db: Session) -> None:
    load(db)
    log_in(client)
    items = db.scalars(
        select(Activity).where(Activity.module_id == 6, Activity.purpose == "mastery")
    ).all()
    for item in items:
        answer(client, item.id, {"submitted": correct_submission(item)})
    report = client.get("/api/me/report").json()
    assert {o["state"] for o in report["objectives"]} == {"met_independently"}
    assert report["ready"] is True
    assert len(report["objectives"]) == 7
