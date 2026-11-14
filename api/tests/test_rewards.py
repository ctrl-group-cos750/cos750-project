"""Private points and badges (FR-9): the rules in app/services/rewards.py, and the API that shows a
student their own."""

import random
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session
from support import open_module

from app.models import Activity, Attempt, HintView, PointsEntry, PointsRule, User, UserBadge
from app.services import rewards, skills
from app.services.rewards import Mastery

STUDENT = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}
OTHER = {"email": "bob@example.com", "password": "Correct horse 2", "displayName": "Bob"}
MCQ: dict[str, Any] = {
    "kind": "multiple_choice",
    "title": "Which vertex is next?",
    "visible": True,
    "config": {
        "prompt": "Next?",
        "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
    },
    "solution": {"correct": "a", "feedback": {}},
}
RIGHT = {"submitted": {"selected": "a"}}
WRONG = {"submitted": {"selected": "b"}}


@pytest.fixture
def user(db: Session) -> User:
    """A student, and two real activities for their attempts: SQLite doesn't enforce an attempt's
    foreign key to its activity, Postgres does (review of 13 Nov on #221: CI failed there)."""
    student = User(email="s@example.com", display_name="S", password_hash="x")  # noqa: S106
    db.add(student)
    db.add_all([Activity(**MCQ), Activity(**MCQ)])
    db.flush()
    return student


def activity_id(db: Session, n: int) -> int:
    """The id of the fixture's `n`th activity (1 or 2)."""
    return list(db.scalars(select(Activity.id).order_by(Activity.id)))[n - 1]


def badges(db: Session, user_id: int) -> dict[tuple[str, str], str | None]:
    return {(b.badge, b.ref): b.tier for b in rewards.badges_of(db, user_id)}


def all_met(result: Mastery = "supported") -> dict[int, Mastery]:
    return dict.fromkeys(rewards.OBJECTIVES, result)


# --- Activity points (FR-9.1, FR-9.2) -----------------------------------------------------------


def attempt(
    db: Session, user: User, *, correct: bool, hint_level: int = 0, activity: int = 1
) -> int:
    row = Attempt(
        user_id=user.id,
        activity_id=activity_id(db, activity),
        submitted={},
        correct=correct,
        score=1.0 if correct else 0.0,
        detail={},
        hint_level=hint_level,
    )
    db.add(row)
    db.flush()
    return rewards.on_attempt(db, row).points


def test_a_first_correct_answer_earns_the_full_points(db: Session, user: User) -> None:
    assert attempt(db, user, correct=True) == 10


@pytest.mark.parametrize(("level", "points"), [(1, 10), (2, 10), (3, 4), (4, 0)])
def test_hint_level_3_earns_fewer_points_and_the_worked_answer_none(
    db: Session, user: User, level: int, points: int
) -> None:
    """After hint 4, the worked answer, the answer is the hint's: it never counts (FR-9.6)."""
    assert attempt(db, user, correct=True, hint_level=level) == points


def test_wrong_answers_never_cost_points(db: Session, user: User) -> None:
    assert attempt(db, user, correct=True) == 10
    assert attempt(db, user, correct=False) == 0
    assert rewards.total_points(db, user.id) == 10


@pytest.mark.parametrize("hint_level", [0, 3])
def test_a_right_answer_after_a_wrong_first_attempt_earns_nothing(
    db: Session, user: User, hint_level: int
) -> None:
    """Review of 13 Nov, High 7: paying the later right answer paid guessing (module 1 all wrong
    then right earned 165 points, all right first time 125). Only a right first attempt earns."""
    assert attempt(db, user, correct=False) == 0
    assert attempt(db, user, correct=True, hint_level=hint_level) == 0
    assert attempt(db, user, correct=True, activity=2) == 10
    assert rewards.total_points(db, user.id) == 10


def test_answering_an_activity_again_earns_nothing_more(db: Session, user: User) -> None:
    attempt(db, user, correct=True, hint_level=3)
    assert attempt(db, user, correct=True) == 0
    assert attempt(db, user, correct=True, activity=2) == 10
    assert rewards.total_points(db, user.id) == 14


def test_points_follow_the_rules_table(db: Session, user: User) -> None:
    db.add(PointsRule(event="activity_correct", points=7))
    db.flush()
    assert attempt(db, user, correct=True) == 7


def test_a_missing_rule_falls_back_to_the_documented_points(db: Session, user: User) -> None:
    assert rewards.points_for(db, "bonus_quest") == 20


# --- Objective badges and points (FR-9.3) -------------------------------------------------------


def test_met_with_support_earns_bronze_and_15_points(db: Session, user: User) -> None:
    earned = rewards.on_objective_result(db, user.id, 5, "supported", {})
    assert earned.points == 15
    assert [(b.badge, b.tier) for b in earned.badges] == [("lo5", "bronze")]


def test_met_independently_earns_gold_and_30_points(db: Session, user: User) -> None:
    earned = rewards.on_objective_result(db, user.id, 5, "independent", {})
    assert earned.points == 30
    assert badges(db, user.id) == {("lo5", ""): "gold"}


def test_bronze_goes_up_to_gold_and_the_points_are_topped_up(db: Session, user: User) -> None:
    rewards.on_objective_result(db, user.id, 5, "supported", {})
    rewards.mark_seen(db, user.id)
    earned = rewards.on_objective_result(db, user.id, 5, "independent", {})
    assert earned.points == 15  # 15 + 15: the same 30 as meeting it alone first time
    assert rewards.total_points(db, user.id) == 30
    (badge,) = earned.badges
    assert badge.tier == "gold"
    assert badge.upgraded_at is not None
    assert badge.seen_at is None  # announced again


def test_a_badge_never_goes_down_or_away(db: Session, user: User) -> None:
    rewards.on_objective_result(db, user.id, 5, "independent", {})
    assert rewards.on_objective_result(db, user.id, 5, "not_yet", {}) == rewards.Earned()
    assert rewards.on_objective_result(db, user.id, 5, "supported", {}) == rewards.Earned()
    assert badges(db, user.id) == {("lo5", ""): "gold"}
    assert rewards.total_points(db, user.id) == 30


# --- Badge levels: practised, bronze, gold (#214) ----------------------------------------------


def test_practised_is_the_first_level_and_earns_no_points(db: Session, user: User) -> None:
    earned = rewards.on_practised(db, user.id, 5)
    assert earned.points == 0
    assert [(b.badge, b.tier) for b in earned.badges] == [("lo5", "practised")]
    assert rewards.on_practised(db, user.id, 5) == rewards.Earned()  # once
    assert rewards.total_points(db, user.id) == 0


@pytest.mark.parametrize(
    ("result", "tier", "points"), [("supported", "bronze", 15), ("independent", "gold", 30)]
)
def test_the_mastery_check_raises_practised(
    db: Session, user: User, result: Mastery, tier: str, points: int
) -> None:
    rewards.on_practised(db, user.id, 5)
    rewards.mark_seen(db, user.id)
    earned = rewards.on_objective_result(db, user.id, 5, result, {})
    assert earned.points == points  # the objective's points in full: nothing lost on the way up
    (badge,) = earned.badges
    assert (badge.tier, badge.seen_at) == (tier, None)  # announced again, at its new level
    assert badge.upgraded_at is not None
    assert badges(db, user.id) == {("lo5", ""): tier}


@pytest.mark.parametrize("held", ["supported", "independent"])
def test_practised_never_lowers_a_badge(db: Session, user: User, held: Mastery) -> None:
    rewards.on_objective_result(db, user.id, 5, held, {})
    before = badges(db, user.id)
    assert rewards.on_practised(db, user.id, 5) == rewards.Earned()
    assert badges(db, user.id) == before


def test_not_yet_keeps_practised(db: Session, user: User) -> None:
    rewards.on_practised(db, user.id, 5)
    assert rewards.on_objective_result(db, user.id, 5, "not_yet", {}) == rewards.Earned()
    assert badges(db, user.id) == {("lo5", ""): "practised"}


def test_practised_needs_a_real_objective(db: Session, user: User) -> None:
    with pytest.raises(ValueError, match="objective 9"):
        rewards.on_practised(db, user.id, 9)


def test_not_yet_earns_nothing(db: Session, user: User) -> None:
    assert rewards.on_objective_result(db, user.id, 5, "not_yet", {}) == rewards.Earned()
    assert badges(db, user.id) == {}


def test_an_unknown_objective_is_refused(db: Session, user: User) -> None:
    with pytest.raises(ValueError, match="No learning objective 9"):
        rewards.on_objective_result(db, user.id, 9, "supported", {})


def test_ready_for_the_lecture_when_no_objective_is_not_yet(db: Session, user: User) -> None:
    results = all_met()
    results[8] = "not_yet"
    rewards.on_objective_result(db, user.id, 7, "supported", results)
    assert ("ready-for-lecture", "") not in badges(db, user.id)
    earned = rewards.on_objective_result(db, user.id, 8, "supported", results)
    assert ("ready-for-lecture", "") in {(b.badge, b.ref) for b in earned.badges}
    assert ("solo-run", "") not in badges(db, user.id)


def test_solo_run_when_every_objective_is_met_independently(db: Session, user: User) -> None:
    rewards.on_objective_result(db, user.id, 1, "independent", all_met("independent"))
    assert {("ready-for-lecture", ""), ("solo-run", "")} <= badges(db, user.id).keys()


def test_came_back_stronger_only_through_the_review_path(db: Session, user: User) -> None:
    rewards.on_objective_result(db, user.id, 3, "supported", {})
    assert ("came-back-stronger", "") not in badges(db, user.id)
    rewards.on_objective_result(db, user.id, 4, "supported", {}, via_review=True)
    assert ("came-back-stronger", "") in badges(db, user.id)


# --- Modules, quests and the hidden badge --------------------------------------------------------


def test_a_module_earns_25_points_once(db: Session, user: User) -> None:
    assert rewards.on_module_completed(db, user.id, 2).points == 25
    assert rewards.on_module_completed(db, user.id, 2).points == 0


def test_each_bonus_quest_earns_its_own_badge_then_all_quests(db: Session, user: User) -> None:
    assert rewards.on_bonus_quest(db, user.id, 1, all_quests_done=False).points == 20
    rewards.on_bonus_quest(db, user.id, 2, all_quests_done=True)
    assert badges(db, user.id).keys() == {("quest", "1"), ("quest", "2"), ("all-quests", "")}
    assert rewards.on_bonus_quest(db, user.id, 2, all_quests_done=True) == rewards.Earned()


def test_the_first_module_badge_comes_with_the_first_module_only(db: Session, user: User) -> None:
    assert [b.badge for b in rewards.on_module_completed(db, user.id, 0).badges] == ["first-module"]
    assert rewards.on_module_completed(db, user.id, 1).badges == ()


def test_every_awarded_badge_is_in_the_catalogue() -> None:
    assert len(rewards.BADGES) == 14
    assert {f"lo{n}" for n in range(1, 9)} <= rewards.BADGES


# --- The API -------------------------------------------------------------------------------------


def log_in(client: TestClient, who: dict[str, str] = STUDENT) -> None:
    assert client.post("/api/auth/register", json=who).status_code == 201


def student_id(db: Session, email: str = "ada@example.com") -> int:
    found = db.scalar(select(User.id).where(User.email == email))
    assert found is not None
    return found


def test_rewards_need_a_login(client: TestClient, db: Session) -> None:
    assert client.get("/api/rewards").status_code == 401
    assert client.post("/api/rewards/seen").status_code == 401
    assert client.put("/api/rewards/settings", json={"hideRewards": True}).status_code == 401


def test_a_new_student_has_no_points_or_badges(client: TestClient, db: Session) -> None:
    log_in(client)
    assert client.get("/api/rewards").json() == {"hideRewards": False, "points": 0, "badges": []}


def test_a_correct_answer_shows_up_as_points(client: TestClient, db: Session) -> None:
    activity = Activity(**MCQ, module_id=open_module(db))
    db.add(activity)
    db.commit()
    log_in(client)
    client.post(f"/api/activities/{activity.id}/attempts", json=RIGHT)
    client.post(f"/api/activities/{activity.id}/attempts", json=WRONG)
    client.post(f"/api/activities/{activity.id}/attempts", json=RIGHT)
    assert client.get("/api/rewards").json()["points"] == 10


@pytest.mark.parametrize(("level", "points"), [(3, 4), (4, 0)])
def test_a_correct_answer_after_hint_3_earns_4_and_after_the_worked_solution_nothing(
    client: TestClient, db: Session, level: int, points: int
) -> None:
    activity = Activity(**MCQ, module_id=open_module(db))
    db.add(activity)
    db.commit()
    log_in(client)
    db.add(HintView(user_id=student_id(db), activity_id=activity.id, level=level))
    db.commit()
    client.post(f"/api/activities/{activity.id}/attempts", json=RIGHT)
    assert client.get("/api/rewards").json()["points"] == points


def test_new_badges_are_announced_once(client: TestClient, db: Session) -> None:
    log_in(client)
    rewards.on_objective_result(db, student_id(db), 5, "supported", {})
    db.commit()
    (badge,) = client.get("/api/rewards").json()["badges"]
    assert badge["badge"] == "lo5"
    assert badge["tier"] == "bronze"
    assert badge["seen"] is False
    seen = client.post("/api/rewards/seen").json()
    assert seen["badges"][0]["seen"] is True
    assert client.get("/api/rewards").json()["badges"][0]["seen"] is True


def test_a_student_only_ever_sees_their_own(client: TestClient, db: Session) -> None:
    log_in(client, OTHER)
    rewards.on_objective_result(db, student_id(db, "bob@example.com"), 1, "independent", {})
    db.commit()
    client.post("/api/auth/logout")
    log_in(client)
    assert client.get("/api/rewards").json() == {"hideRewards": False, "points": 0, "badges": []}


def test_hiding_rewards_keeps_earning_them_quietly(client: TestClient, db: Session) -> None:
    log_in(client)
    res = client.put("/api/rewards/settings", json={"hideRewards": True})
    assert res.json()["hideRewards"] is True
    rewards.on_objective_result(db, student_id(db), 2, "supported", {})
    db.commit()
    shown = client.put("/api/rewards/settings", json={"hideRewards": False}).json()
    assert shown["hideRewards"] is False
    assert shown["points"] == 15
    assert [(b["badge"], b["seen"]) for b in shown["badges"]] == [("lo2", True)]


def test_the_setting_refuses_anything_else(client: TestClient, db: Session) -> None:
    log_in(client)
    assert (
        client.put("/api/rewards/settings", json={"hideRewards": "yes please"}).status_code == 422
    )
    assert client.put("/api/rewards/settings", json={"points": 9999}).status_code == 422


def test_rows_are_never_negative_or_duplicated(db: Session, user: User) -> None:
    for _ in range(3):
        attempt(db, user, correct=True)
        rewards.on_objective_result(db, user.id, 1, "independent", all_met("independent"))
    entries = db.scalars(select(PointsEntry).where(PointsEntry.user_id == user.id)).all()
    assert all(e.points > 0 for e in entries)
    assert len({e.ref for e in entries}) == len(entries)
    held = db.scalars(select(UserBadge).where(UserBadge.user_id == user.id)).all()
    assert len({(b.badge, b.ref) for b in held}) == len(held)


# --- The evidence rule over many activities (#221 re-review) -------------------------------------


def _random_history(db: Session, user_id: int, ids: list[int], rng: random.Random) -> None:
    """Hints in rounds and wrong and right answers, in a random order, on both activities."""
    last = db.scalar(select(func.max(Attempt.id))) or 0
    shown: set[tuple[int, int, int]] = set()  # (activity, level, round)
    for _ in range(rng.randint(0, 7)):
        activity = rng.choice(ids)
        if rng.random() < 0.5:
            level, round_ = rng.randint(1, 4), rng.randint(0, 1)
            if (activity, level, round_) in shown:
                continue
            shown.add((activity, level, round_))
            db.add(
                HintView(
                    user_id=user_id,
                    activity_id=activity,
                    level=level,
                    round=round_,
                    after_attempt=last,
                )
            )
        else:
            correct = rng.random() < 0.6
            row = Attempt(
                user_id=user_id,
                activity_id=activity,
                submitted={},
                correct=correct,
                score=1.0 if correct else 0.0,
                detail={},
                hint_level=rng.choice((0, 0, 1, 2, 3, 4)),
            )
            db.add(row)
            db.flush()
            last = row.id
    db.flush()


def test_the_one_query_rule_matches_real_work_on_every_history(db: Session, user: User) -> None:
    """`first_answers` must give the same sets as `real_work` applied to each first attempt, and
    "first time" must be that before any hint: so points and the skill profile can't drift."""
    rng = random.Random(221)  # noqa: S311 - a reproducible draw, not security
    uid = user.id
    ids = [activity_id(db, 1), activity_id(db, 2)]
    for _ in range(200):
        nested = db.begin_nested()
        _random_history(db, uid, ids, rng)
        firsts = db.scalars(
            select(Attempt).where(Attempt.id.in_(rewards.first_tries(db, uid, ids)))
        ).all()
        own = {a.activity_id for a in firsts if rewards.real_work(db, a)}
        first_time = {
            a.activity_id
            for a in firsts
            if a.activity_id in own
            and a.hint_level == 0
            and not rewards.answer_given_away(db, uid, a.activity_id, before=a.id, level=1)
        }
        got = rewards.first_answers(db, uid, ids)
        assert got.on_own == own
        assert got.first_time == first_time
        assert rewards.real_work_on(db, uid, ids) == own
        nested.rollback()
        # SQLite hands the rolled-back ids out again: forget the objects that held them.
        db.expunge_all()


def test_real_work_on_is_one_query_however_many_activities(db: Session, user: User) -> None:
    for n in (1, 2):
        attempt(db, user, correct=True, activity=n)
    statements: list[str] = []
    listen = event.listens_for(db.get_bind(), "before_cursor_execute")

    @listen
    def count(*args: Any) -> None:
        statements.append(args[2])

    try:
        rewards.real_work_on(db, user.id, [activity_id(db, 1), activity_id(db, 2)])
        # activity_id() above runs its own query; count only the call itself.
        statements.clear()
        rewards.real_work_on(db, user.id, [1, 2, 3, 4, 5, 6, 7, 8])
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", count)
    assert len(statements) == 1


def test_the_skill_profiles_query_gives_the_same_rule_for_medals(db: Session, user: User) -> None:
    """Medals use the skill profile's own query (`skills._answers`, which can also work per round);
    with the first attempt ever it must give exactly `first_answers`, which points use, so medals
    and points can't drift apart (#222 merge with #221)."""
    rng = random.Random(222)  # noqa: S311 - a reproducible draw, not security
    uid = user.id
    activities = list(db.scalars(select(Activity).order_by(Activity.id)))
    ids = [a.id for a in activities]
    for _ in range(200):
        nested = db.begin_nested()
        _random_history(db, uid, ids, rng)
        theirs = rewards.first_answers(db, uid, ids)
        ours = skills._answers(db, uid, activities)
        assert (ours.on_own, ours.first_time) == (theirs.on_own, theirs.first_time)
        nested.rollback()
        db.expunge_all()
        activities = list(db.scalars(select(Activity).order_by(Activity.id)))
