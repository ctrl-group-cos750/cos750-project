"""The mastery check and report (FR-7.1 to FR-7.4, FR-7.6): the rules in app/services/mastery.py,
the stored results and what they earn, and GET /api/me/report."""

import json
import os
import threading
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, HintView, ObjectiveResult, Segment, User
from app.schemas.activities import FixTheBugSolution, ParsonsSolution
from app.schemas.graphs import GraphScenarioOut
from app.seed import FixtureFile, ObjectiveFixture, check_references, load, read_fixtures
from app.services import mastery, rewards
from app.services.attempts import record_attempt
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


def test_an_objective_needs_a_badge_so_9_is_refused() -> None:
    # The badge catalogue has lo1 to lo8; meeting a 9th would have no badge to award.
    with pytest.raises(ValueError, match="less than or equal to 8"):
        ObjectiveFixture(id=9, text="t", bloom_level="b", criterion="c", pass_fraction=1.0)


def test_every_objective_needs_a_module_6_item() -> None:
    course = small_course()
    course["activities"] = [a for a in course["activities"] if a["id"] != 603]
    with pytest.raises(ValueError, match=r"no mastery item for objectives \[2\]"):
        check_references(FixtureFile.model_validate(course))


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


def mcq(
    id: int, objective: int, purpose: str = "mastery", module: int | None = 6
) -> dict[str, Any]:
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


def ladder() -> list[dict[str, Any]]:
    """The full hint ladder a practice item on a review path needs: a new list each time."""
    return [{"level": n, "body": f"Hint {n}"} for n in (1, 2, 3, 4)]


def review_path(objective: int, fresh: list[int]) -> dict[str, Any]:
    """A worked example, practice item `objective`01, then the fresh items."""
    base = 1000 + 100 * objective
    return {
        "objective_id": objective,
        "segments": [
            {"id": base, "kind": "worked_example", "title": "Again", "body": "Like this."},
            {"id": base + 1, "kind": "activity", "title": "Practice", "activity_id": base + 1},
        ]
        + [{"id": i, "kind": "activity", "title": f"Fresh {i}", "activity_id": i} for i in fresh],
    }


def small_course(rule_1: dict[str, Any] | None = None) -> dict[str, Any]:
    """Objective 1 needs 2 of 2 MCQs (601, 602), objective 2 one MCQ (603); 301 is practice, so it
    doesn't count. The review paths: objective 1 practises on 1101, then fresh 1102 and 1103;
    objective 2 practises on 1201, then fresh 1202."""
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
            mcq(1101, 1, purpose="review", module=None) | {"hints": ladder()},
            mcq(1102, 1, module=None),
            mcq(1103, 1, module=None),
            mcq(1201, 2, purpose="review", module=None) | {"hints": ladder()},
            mcq(1202, 2, module=None),
        ],
        "review_paths": [review_path(1, [1102, 1103]), review_path(2, [1202])],
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
        "review": None,
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
        case "parsons":
            return {"order": ParsonsSolution.model_validate(solution).first_order()}
        case "fix_the_bug":
            return {"order": FixTheBugSolution.model_validate(solution).first_order()}
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
    covered = {
        a.objective_id for a in content.activities if a.module_id == 6 and a.purpose == "mastery"
    }
    assert covered == {o.id for o in content.objectives}
    shown = {s.activity_id for m in content.modules if m.id == 6 for s in m.segments}
    assert {
        a.id for a in content.activities if a.module_id == 6 and a.purpose == "mastery"
    } <= shown


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


# One accepted order of module 6's Parsons item that is not the worked example's: the starting
# values reversed, and queue.append before visited.add.
EQUIVALENT_BFS = [1, 2, 5, 4, 3, 6, 7, 8, 9, 10, 12, 11, 13]


def answer_module_6(client: TestClient, db: Session, parsons_order: list[int]) -> Activity:
    """Answer every module 6 mastery item right, except that the Parsons item gets
    `parsons_order`. Returns the Parsons item."""
    items = db.scalars(
        select(Activity).where(Activity.module_id == 6, Activity.purpose == "mastery")
    ).all()
    parsons = next(i for i in items if i.kind == "parsons")
    for item in items:
        body = {"order": parsons_order} if item is parsons else correct_submission(item)
        answer(client, item.id, {"submitted": body})
    return parsons


def test_objective_6_is_met_by_any_accepted_bfs_order(client: TestClient, db: Session) -> None:
    """Objective 6 needs every part right (pass_fraction 1.0): an order that is correct but not
    the worked example's must not decide it (FR-5.4, #145)."""
    load(db)
    log_in(client)
    parsons = answer_module_6(client, db, EQUIVALENT_BFS)
    assert parsons.objective_id == 6
    stored = db.scalars(select(Attempt).where(Attempt.activity_id == parsons.id)).one()
    assert stored.correct
    assert stored.score == 1.0
    assert len(stored.detail["parts"]) == 13  # one per line, as for the worked example's order
    report = client.get("/api/me/report").json()
    assert {o["state"] for o in report["objectives"]} == {"met_independently"}
    assert report["ready"] is True


def test_one_misplaced_line_in_objective_6_is_not_yet(client: TestClient, db: Session) -> None:
    """One line out of place is one wrong part of 13, not every line after it: still "not yet"
    on objective 6, which needs all of them, and nothing else changes."""
    load(db)
    log_in(client)
    misplaced = [1, 2, 3, 4, 5, 6, 7, 8, 13, 9, 10, 11, 12]  # return order inside the loop's place
    parsons = answer_module_6(client, db, misplaced)
    stored = db.scalars(select(Attempt).where(Attempt.activity_id == parsons.id)).one()
    assert [p["correct"] for p in stored.detail["parts"]].count(False) == 1
    assert stored.score == pytest.approx(12 / 13)
    got = states(client)
    assert got[6] == "not_yet"
    assert {s for o, s in got.items() if o != 6} == {"met_independently"}


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="needs Postgres row locks")
def test_two_first_answers_at_once_both_record(course: Path, db: Session) -> None:
    """Two mastery answers from one student in two transactions at once: the second waits for the
    first's lock instead of failing on the unique (user, objective) row both would insert."""
    student = User(email="z@example.com", display_name="Z", password_hash="x")  # noqa: S106
    db.add(student)
    db.commit()
    engine = db.get_bind()
    errors: list[BaseException] = []

    with Session(engine) as first:
        record_attempt(first, student.id, first.get_one(Activity, 601), {"selected": "a"})

        def second() -> None:
            try:
                with Session(engine) as other:
                    activity = other.get_one(Activity, 603)
                    record_attempt(other, student.id, activity, {"selected": "a"})
                    other.commit()
            except BaseException as exc:  # reported below, from the test's thread
                errors.append(exc)

        racer = threading.Thread(target=second)
        racer.start()
        racer.join(timeout=1)
        assert racer.is_alive(), "the second answer should wait for the first's lock"
        first.commit()
        racer.join(timeout=10)

    assert errors == []
    db.expire_all()
    rows = db.scalars(select(ObjectiveResult).where(ObjectiveResult.user_id == student.id)).all()
    assert {r.objective_id: r.state for r in rows} == {1: "not_attempted", 2: "met_independently"}


# --- The review path (FR-7.5, ID document §7.6) --------------------------------------------------


def broken(change: Any) -> dict[str, Any]:
    course = small_course()
    change(course)
    return course


def _path(course: dict[str, Any], objective: int) -> dict[str, Any]:
    return next(p for p in course["review_paths"] if p["objective_id"] == objective)


def _fresh_first(path: dict[str, Any]) -> None:
    """Keep the worked example first, but put the fresh items before the practice."""
    teach, *rest = path["segments"]
    path["segments"] = [teach, *reversed(rest)]


def _activity(course: dict[str, Any], id: int) -> dict[str, Any]:
    return next(a for a in course["activities"] if a["id"] == id)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda c: c["review_paths"].pop(), r"no review path: \[2\]"),
        (lambda c: c["review_paths"].append(review_path(2, [])), "two review paths"),
        (lambda c: _path(c, 2).update(objective_id=3), "objectives that don't exist"),
        (lambda c: _activity(c, 1202).update(module_id=6), "must have no module"),
        (lambda c: _activity(c, 1202).update(objective_id=1), "must have no module"),
        (lambda c: _activity(c, 1201).update(purpose="practice"), "is practice"),
        (lambda c: _path(c, 2)["segments"].pop(), "at least one fresh mastery item"),
        (lambda c: _path(c, 2)["segments"].pop(1), "at least one practice"),
        (lambda c: _activity(c, 1201)["hints"].pop(), "needs the full hint ladder"),
        (lambda c: _fresh_first(_path(c, 1)), "after all the practice"),
        (lambda c: _path(c, 2)["segments"].append(_path(c, 2)["segments"][-1]), "path twice"),
        (lambda c: _path(c, 2)["segments"][1].update(activity_id=999), "no activity 999"),
        (
            lambda c: _path(c, 2)["segments"][0].update(skip_check_activity_id=603),
            "nothing on a review path is skipped",
        ),
        (
            lambda c: c["activities"].append(mcq(399, 1, module=3)),
            "mastery item belongs in module 6 or on a review path",
        ),
        (
            lambda c: c["modules"][0].update(
                segments=[{"id": 9, "kind": "activity", "title": "x", "activity_id": 1202}]
            ),
            "is on a review path",
        ),
    ],
)
def test_a_review_path_that_cannot_work_is_refused(change: Any, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        check_references(FixtureFile.model_validate(broken(change)))


@pytest.mark.parametrize(
    ("segments", "message"),
    [
        ([{"id": 1, "kind": "activity", "title": "x", "activity_id": 1}], "teaches the objective"),
        (
            [
                {"id": 1, "kind": "activity", "title": "x", "activity_id": 1},
                {"id": 2, "kind": "worked_example", "title": "y", "body": "b"},
            ],
            "starts with a segment that teaches",
        ),
        (
            [{"id": 1, "kind": "refresher", "title": "x", "body": "b", "refresher_for": "q"}],
            "belongs in module 0",
        ),
    ],
)
def test_a_review_path_teaches_before_it_tests(segments: list[Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        FixtureFile.model_validate({"review_paths": [{"objective_id": 1, "segments": segments}]})


def test_review_path_segment_ids_must_not_collide_with_modules(tmp_path: Path) -> None:
    course = small_course()
    _path(course, 2)["segments"][0]["id"] = 1100  # objective 1's worked example
    (tmp_path / "course.json").write_text(json.dumps(course), encoding="utf-8")
    with pytest.raises(ValueError, match=r"segment ids used twice: \[1100\]"):
        read_fixtures(tmp_path)


def test_a_segment_belongs_to_a_module_or_a_review_path(course: Path, db: Session) -> None:
    db.add(Segment(id=5000, kind="text", title="Nowhere", body="b"))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
    db.add(
        Segment(id=5001, module_id=3, review_objective_id=1, kind="text", title="Both", body="b")
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_a_reseed_reorders_and_removes_review_segments(course: Path, db: Session) -> None:
    changed = small_course()
    segments = _path(changed, 1)["segments"]
    segments[:] = [segments[0], segments[1], segments[3]]  # drop fresh item 1102's step
    (course / "course.json").write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="activity 1102: a mastery item belongs"):
        load(db, course)
    changed["activities"] = [a for a in changed["activities"] if a["id"] != 1102]
    (course / "course.json").write_text(json.dumps(changed), encoding="utf-8")
    load(db, course)
    db.expire_all()
    rows = db.scalars(
        select(Segment).where(Segment.review_objective_id == 1).order_by(Segment.position)
    ).all()
    assert [(s.id, s.position, s.module_id) for s in rows] == [
        (1100, 1, None),
        (1101, 2, None),
        (1103, 3, None),
    ]


def fail_objective_2(client: TestClient) -> None:
    answer(client, 603, WRONG)


def test_a_review_path_is_closed_until_module_6_says_not_yet(
    client: TestClient, course: Path
) -> None:
    log_in(client)
    assert client.get("/api/me/review/2").status_code == 403
    for item in (1201, 1202):
        assert client.get(f"/api/activities/{item}").status_code == 403
        assert client.post(f"/api/activities/{item}/attempts", json=RIGHT).status_code == 403
        assert client.post(f"/api/activities/{item}/hints").status_code == 403
    assert states(client)[2] == "not_attempted"


def test_an_objective_met_in_module_6_never_opens_its_path(
    client: TestClient, course: Path
) -> None:
    log_in(client)
    answer(client, 603)
    assert client.get("/api/me/review/2").status_code == 403
    assert client.get("/api/me/report").json()["objectives"][1]["review"] is None


def test_an_objective_without_a_path_is_404(client: TestClient, course: Path) -> None:
    log_in(client)
    assert client.get("/api/me/review/9").status_code == 404


def test_not_yet_opens_the_review_path(client: TestClient, course: Path) -> None:
    log_in(client)
    fail_objective_2(client)
    report = client.get("/api/me/report").json()
    assert report["objectives"][1]["review"] == {"answered": 0, "total": 1}
    path = client.get("/api/me/review/2").json()
    assert path["objectiveId"] == 2
    assert path["state"] == "not_yet"
    assert path["progress"] == {"answered": 0, "total": 1}
    assert [(s["kind"], s["activityId"], s["purpose"], s["answered"]) for s in path["steps"]] == [
        ("worked_example", None, None, False),
        ("activity", 1201, "review", False),
        ("activity", 1202, "mastery", False),
    ]
    assert path["steps"][0]["body"] == "Like this."
    assert client.get("/api/activities/1202").status_code == 200


def test_practice_on_the_path_does_not_change_the_result(client: TestClient, course: Path) -> None:
    log_in(client)
    fail_objective_2(client)
    answer(client, 1201)
    assert states(client)[2] == "not_yet"
    steps = client.get("/api/me/review/2").json()["steps"]
    assert [s["answered"] for s in steps] == [False, True, False]


def test_the_fresh_items_decide_the_result_and_the_student_comes_back_stronger(
    client: TestClient, course: Path, db: Session
) -> None:
    user = log_in(client)
    answer(client, 601)
    answer(client, 602)
    fail_objective_2(client)
    assert client.get("/api/me/report").json()["ready"] is False
    answer(client, 1201, WRONG)  # practice: getting it wrong costs nothing
    answer(client, 1202)
    report = client.get("/api/me/report").json()
    assert states(client) == {1: "met_independently", 2: "met_independently"}
    assert report["ready"] is True
    assert report["objectives"][1]["review"] == {"answered": 1, "total": 1}
    held = {b.badge for b in rewards.badges_of(db, user)}
    assert {rewards.CAME_BACK_STRONGER, rewards.READY_FOR_LECTURE} <= held
    stored = db.scalar(
        select(ObjectiveResult).where(
            ObjectiveResult.user_id == user, ObjectiveResult.objective_id == 2
        )
    )
    assert stored is not None
    assert len(stored.evidence) == 2  # module 6's attempt and the fresh item's
    # The path stays open to look back at.
    assert client.get("/api/me/review/2").json()["state"] == "met_independently"


def test_all_fresh_items_must_be_answered_before_they_decide(
    client: TestClient, course: Path
) -> None:
    log_in(client)
    answer(client, 601)
    answer(client, 602, WRONG)
    answer(client, 1102)
    assert states(client)[1] == "not_yet"  # module 6's result stands until 1103 is answered
    assert client.get("/api/me/report").json()["objectives"][0]["review"] == {
        "answered": 1,
        "total": 2,
    }
    answer(client, 1103)
    assert states(client)[1] == "met_independently"


def test_still_not_yet_after_the_path(client: TestClient, course: Path) -> None:
    log_in(client)
    fail_objective_2(client)
    answer(client, 1202, WRONG)
    answer(client, 1202, RIGHT)  # only the first answer to a fresh item counts too
    report = client.get("/api/me/report").json()
    assert states(client)[2] == "not_yet"
    assert report["objectives"][1]["review"] == {"answered": 1, "total": 1}


def test_hint_3_on_a_fresh_item_makes_it_met_with_support(
    client: TestClient, course: Path, db: Session
) -> None:
    user = log_in(client)
    fail_objective_2(client)
    db.add(HintView(user_id=user, activity_id=1202, level=3))
    db.commit()
    answer(client, 1202)
    assert states(client)[2] == "met_with_support"


def wrong_submission(activity: Activity) -> dict[str, Any]:
    """An answer to any committed item that gets every part wrong. Never blank: the server
    refuses a blank answer without recording it (#143)."""
    wrong: dict[str, dict[str, Any]] = {
        "multiple_choice": {"selected": "not-an-option"},
        "matching": {"pairs": {"no-such-item": "no-such-match"}},
        "parsons": {"order": [-1]},
        "fix_the_bug": {"order": [-1]},
        "fill_in": {"answers": {-1: "no-such-token"}},
        "choose_tests": {"selected": ["no-such-test"]},
        "trace": {"rows": [{"visitedVertex": "Z", "queue": [], "visited": [], "order": []}]},
    }
    return wrong[activity.kind]


def test_every_committed_objective_has_a_review_path_that_teaches_then_tests() -> None:
    content = read_fixtures()
    activities = {a.id: a for a in content.activities}
    paths = {r.objective_id: r for r in content.review_paths}
    assert set(paths) == {o.id for o in content.objectives}
    for objective, path in paths.items():
        kinds = [s.kind for s in path.segments]
        assert kinds[0] == "worked_example", objective
        purposes = [activities[s.activity_id].purpose for s in path.segments if s.activity_id]
        assert purposes[0] == "review", objective  # practice, with the full hint ladder
        assert len(activities[path.segments[1].activity_id or 0].hints) == 4, objective
        assert purposes[-1] == "mastery", objective


def test_the_committed_review_paths_can_take_a_student_to_ready(
    client: TestClient, db: Session
) -> None:
    load(db)
    log_in(client)
    check = db.scalars(
        select(Activity).where(Activity.module_id == 6, Activity.purpose == "mastery")
    ).all()
    for item in check:
        answer(client, item.id, {"submitted": wrong_submission(item)})
    assert set(states(client).values()) == {"not_yet"}
    for objective in range(1, 8):
        for step in client.get(f"/api/me/review/{objective}").json()["steps"]:
            if step["purpose"] == "mastery":
                item = db.get_one(Activity, step["activityId"])
                answer(client, item.id, {"submitted": correct_submission(item)})
    report = client.get("/api/me/report").json()
    assert set(states(client).values()) == {"met_independently"}
    assert report["ready"] is True
