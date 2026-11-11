"""The one-off re-grade of Parsons and fix-the-bug attempts (app/regrade.py, #145): attempts stored
by the one-order checker are graded again, results follow, rewards are never taken back, and a
second run changes nothing."""

import os
import threading
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from test_mastery import correct_submission

import app.db
from app import regrade
from app.models import Activity, Attempt, ObjectiveResult, PointsEntry, User, UserBadge
from app.schemas.activities import FixTheBugSolution, ParsonsSolution
from app.seed import load
from app.services import mastery
from app.services.attempts import record_attempt
from app.services.mastery import evaluate, recompute

# A correct order of 619 that the one-order checker marked wrong, and a really wrong one.
EQUIVALENT = [1, 2, 5, 4, 3, 6, 7, 8, 9, 10, 12, 11, 13]
MISPLACED = [1, 2, 3, 4, 5, 6, 7, 8, 13, 9, 10, 11, 12]


def student(db: Session, n: int) -> int:
    user = User(email=f"s{n}@example.com", display_name=f"S{n}", password_hash="x")  # noqa: S106
    db.add(user)
    db.flush()
    return user.id


def stored_as_on_staging(db: Session, user: int, activity: Activity, order: list[int]) -> Attempt:
    """An attempt as the one-order checker stored it, before #145."""
    plain = (
        FixTheBugSolution if activity.kind == "fix_the_bug" else ParsonsSolution
    ).model_validate(activity.solution)
    detail = old_detail(plain.first_order(), order)
    attempt = Attempt(
        user_id=user,
        activity_id=activity.id,
        submitted={"order": order},
        correct=detail["correct"],
        score=detail["score"],
        detail=detail,
    )
    db.add(attempt)
    db.flush()
    return attempt


def old_detail(expected: list[int], got: list[int]) -> dict[str, Any]:
    """What the one-order checker stored before #145: one part per position, right only where
    the id there is the solution's."""
    marks = [
        i < len(got) and i < len(expected) and got[i] == expected[i]
        for i in range(max(len(expected), len(got)))
    ]
    parts = [{"ref": i, "correct": mark, "message": None} for i, mark in enumerate(marks)]
    right = sum(marks)
    return {
        "correct": right == len(parts),
        "score": right / len(parts),
        "parts": parts,
        "feedback": f"{right} of {len(parts)} correct.",
    }


def right(activity: Activity) -> dict[str, Any]:
    return correct_submission(activity)


def take_module_6(db: Session, user: int, parsons_order: list[int]) -> Attempt:
    """Every module 6 mastery item answered right through the real path, except 619, stored as
    staging's checker graded it. Then results computed as staging would have."""
    items = db.scalars(
        select(Activity).where(Activity.module_id == 6, Activity.purpose == "mastery")
    ).all()
    parsons = None
    for item in items:
        if item.id == 619:
            parsons = stored_as_on_staging(db, user, item, parsons_order)
        else:
            record_attempt(db, user, item, right(item))
    assert parsons is not None
    recompute(db, user)
    db.commit()
    return parsons


def state(db: Session, user: int, objective: int) -> str:
    return next(o.state for o in evaluate(db, user) if o.objective.id == objective)


def rewards_held(db: Session, user: int) -> tuple[int, int]:
    points = db.scalar(select(func.count()).where(PointsEntry.user_id == user))
    badges = db.scalar(select(func.count()).where(UserBadge.user_id == user))
    return points or 0, badges or 0


def test_an_equivalent_order_marked_wrong_is_now_correct_and_decides_objective_6(
    db: Session,
) -> None:
    load(db)
    one, two = student(db, 1), student(db, 2)
    first = take_module_6(db, one, EQUIVALENT)
    second = take_module_6(db, two, MISPLACED)
    assert (first.correct, state(db, one, 6)) == (False, "not_yet")  # as on staging
    held = rewards_held(db, one)

    report = regrade.regrade(db)
    db.commit()

    db.refresh(first)
    db.refresh(second)
    assert (first.correct, first.score) == (True, 1.0)
    assert state(db, one, 6) == "met_independently"
    stored = db.scalar(
        select(ObjectiveResult.state).where(
            ObjectiveResult.user_id == one, ObjectiveResult.objective_id == 6
        )
    )
    assert stored == "met_independently"
    # The misplaced answer stays wrong, but now marks only the misplaced line.
    assert second.correct is False
    assert [p["correct"] for p in second.detail["parts"]].count(False) == 1
    assert state(db, two, 6) == "not_yet"
    # Points and badges only grow: the first correct answer to 619, and objective 6's badge.
    points, badges = rewards_held(db, one)
    assert points > held[0]
    assert badges > held[1]
    assert (first.id, one, 619, True) in report.changed
    assert (second.id, two, 619, False) in report.changed
    assert (one, 6, "not_yet", "met_independently") in report.results


def test_a_second_run_changes_nothing(db: Session) -> None:
    load(db)
    one = student(db, 1)
    take_module_6(db, one, EQUIVALENT)
    regrade.regrade(db)
    db.commit()
    held = rewards_held(db, one)
    again = regrade.regrade(db)
    db.commit()
    assert again.changed == []
    assert again.results == []
    assert rewards_held(db, one) == held


def test_an_attempt_on_an_activity_staff_edited_is_left_alone_and_listed(db: Session) -> None:
    """After #128 an edited activity may ask a different question than the stored answer
    answered: the re-grade skips it and names it, and changes nothing else for it."""
    from datetime import UTC, datetime

    load(db)
    one = student(db, 1)
    attempt = take_module_6(db, one, EQUIVALENT)
    activity = db.get_one(Activity, attempt.activity_id)
    activity.edited_at = datetime.now(UTC)
    db.commit()
    stored = (attempt.correct, attempt.score, attempt.detail)
    report = regrade.regrade(db)
    db.commit()
    db.refresh(attempt)
    assert report.edited == [attempt.id]
    assert attempt.id not in [c[0] for c in report.changed]
    assert (attempt.correct, attempt.score, attempt.detail) == stored
    assert "edited by staff (skipped): 1" in report.lines()[0]
    assert f"edited by staff: attempts [{attempt.id}]" in report.lines()


def test_a_student_deleted_before_their_turn_is_passed_over(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.locks import StudentGone, lock_student

    load(db)
    one, two = student(db, 1), student(db, 2)
    take_module_6(db, one, EQUIVALENT)
    take_module_6(db, two, EQUIVALENT)
    db.commit()

    def lock_gone_for_one(session: Session, user_id: int) -> None:
        if user_id == one:
            raise StudentGone(user_id)
        lock_student(session, user_id)

    monkeypatch.setattr("app.regrade.lock_student", lock_gone_for_one)
    report = regrade.regrade(db, "commit")
    assert {c[1] for c in report.changed} == {two}


def test_a_correct_attempt_is_never_lowered_and_rewards_stay(db: Session) -> None:
    """An attempt stored as correct that today's content would mark wrong (say, a solution
    edited since) is kept as it was, and so is everything it earned."""
    load(db)
    one = student(db, 1)
    attempt = take_module_6(db, one, EQUIVALENT)
    attempt.submitted = {"order": MISPLACED}  # stored as correct, but this order is wrong
    attempt.correct, attempt.score = True, 1.0
    attempt.detail = {**attempt.detail, "correct": True, "score": 1.0, "parts": []}
    db.commit()
    regrade.regrade(db)
    db.commit()
    held = rewards_held(db, one)
    report = regrade.regrade(db)
    db.commit()
    db.refresh(attempt)
    assert attempt.correct is True
    assert attempt.id in report.kept
    assert f"kept: attempts [{attempt.id}]" in report.lines()
    assert rewards_held(db, one) == held


def test_other_kinds_and_unreadable_attempts_are_left_alone(db: Session) -> None:
    load(db)
    one = student(db, 1)
    choice = db.get_one(Activity, 601)
    wrong = Attempt(
        user_id=one, activity_id=601, submitted={"selected": "zz"}, correct=False, score=0.0,
        detail={"parts": []},
    )  # fmt: skip
    junk = Attempt(
        user_id=one, activity_id=619, submitted={"order": "not a list"}, correct=False,
        score=0.0, detail={"parts": []},
    )  # fmt: skip
    db.add_all([wrong, junk])
    db.commit()
    report = regrade.regrade(db)
    db.commit()
    assert report.unreadable == [junk.id]
    assert f"unreadable: attempts [{junk.id}]" in report.lines()
    assert report.changed == []
    db.refresh(wrong)
    assert (wrong.detail, choice.kind) == ({"parts": []}, "multiple_choice")


def test_the_command_is_a_dry_run_unless_told_to_apply(
    db: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    load(db)
    one = student(db, 1)
    attempt = take_module_6(db, one, EQUIVALENT)
    monkeypatch.setattr(app.db, "SessionLocal", sessionmaker(bind=db.get_bind()))

    regrade.main([])
    out = capsys.readouterr().out
    assert "attempts re-graded: 1, now correct: 1" in out
    assert "activity 619: 1 attempts, 1 now correct" in out
    assert f"user {one}: attempts [{attempt.id}]" in out
    assert f"user {one}, objective 6: not_yet -> met_independently" in out
    assert "dry run: nothing written" in out
    assert "@" not in out  # ids only, never an email
    db.expire_all()
    assert db.get_one(Attempt, attempt.id).correct is False
    assert state(db, one, 6) == "not_yet"

    regrade.main(["--apply"])
    assert "applied" in capsys.readouterr().out
    db.expire_all()
    assert db.get_one(Attempt, attempt.id).correct is True
    regrade.main(["--apply"])
    assert "attempts re-graded: 0" in capsys.readouterr().out


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="needs Postgres row locks")
def test_a_student_answering_during_the_regrade_waits_and_both_succeed(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The re-grade locks a student before it touches their rows. A student answering 619 at that
    moment (their attempt references the locked user row) waits, then finds the points already
    given: no deadlock, no duplicate points (review of #145, /tmp/a4r2/race.py)."""
    load(db)
    one = student(db, 1)
    stored_as_on_staging(db, one, db.get_one(Activity, 619), EQUIVALENT)
    db.commit()
    engine = db.get_bind()
    locked, release = threading.Event(), threading.Event()
    real = mastery.recompute  # attempts.py holds its own reference, so the student is unpaused

    def paused(session: Session, user_id: int) -> Any:
        locked.set()  # the student is locked and their attempt re-graded, not yet committed
        release.wait(10)
        return real(session, user_id)

    monkeypatch.setattr(mastery, "recompute", paused)
    errors: list[BaseException] = []
    done: dict[str, Any] = {}

    def run_regrade() -> None:
        try:
            with Session(engine) as session:
                done["regrade"] = regrade.regrade(session, "commit")
        except BaseException as exc:
            errors.append(exc)

    def run_student() -> None:
        try:
            with Session(engine) as session:
                activity = session.get_one(Activity, 619)
                _, result = record_attempt(session, one, activity, {"order": list(range(1, 14))})
                session.commit()
                done["student"] = result.correct
        except BaseException as exc:
            errors.append(exc)

    grader = threading.Thread(target=run_regrade)
    grader.start()
    assert locked.wait(10)
    answering = threading.Thread(target=run_student)
    answering.start()
    answering.join(1.0)
    assert answering.is_alive()  # waiting for the re-grade's lock, not racing it
    release.set()
    grader.join(30)
    answering.join(30)
    assert errors == []
    assert done["student"] is True
    assert len(done["regrade"].changed) == 1
    with Session(engine) as session:
        rows = session.scalars(
            select(PointsEntry).where(PointsEntry.user_id == one, PointsEntry.ref == "activity:619")
        ).all()
        assert len(rows) == 1
        assert state(session, one, 6) == "not_attempted"  # the other module 6 items: unanswered
