"""Requests from one student that arrive at the same moment, such as a double-click (#138).

These need a real Postgres: SQLite runs one writer at a time and ignores row locks, so it can't
show a deadlock or a race. They run when TEST_DATABASE_URL is set, as it is in CI."""

import os
import threading
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Activity, Attempt, HintView, Module, ModuleProgress, PointsEntry, User
from app.seed import load
from app.services.attempts import record_attempt, reveal_next_hint
from app.services.modules import save_position

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="needs Postgres (TEST_DATABASE_URL)"
)

TIMES = 8


def at_once(engine: Engine | Connection, action: Callable[[Session], Any]) -> list[BaseException]:
    """Run `action` TIMES at the same moment, each in its own session and transaction, as
    concurrent requests are. Returns the errors raised."""
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    start = threading.Barrier(TIMES)
    errors: list[BaseException] = []

    def run() -> None:
        with sessions() as session:
            start.wait()
            try:
                action(session)
                session.commit()
            except BaseException as exc:
                session.rollback()
                errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(TIMES)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return errors


def student(db: Session) -> int:
    user = User(email="ada@example.com", display_name="Ada", password_hash="x")  # noqa: S106 (test only)
    db.add(user)
    db.commit()
    return user.id


def open_module_6(db: Session, user_id: int) -> None:
    for module in db.scalars(select(Module).where(Module.position < 6)):
        db.add(ModuleProgress(user_id=user_id, module_id=module.id, status="complete"))
    db.commit()


def mastery_items(db: Session) -> list[Activity]:
    return list(
        db.scalars(
            select(Activity)
            .where(Activity.module_id == 6, Activity.purpose == "mastery")
            .where(Activity.kind == "multiple_choice")
            .order_by(Activity.id)
        )
    )


def test_answers_to_the_mastery_check_at_the_same_moment_all_count(db: Session) -> None:
    """Each answer to a mastery item recomputes the student's results under a lock; answers that
    arrived together deadlocked and were lost."""
    load(db)
    user_id = student(db)
    open_module_6(db, user_id)
    items = iter(mastery_items(db)[:TIMES])

    def answer(session: Session) -> None:
        activity = session.get_one(Activity, next(items).id)
        record_attempt(session, user_id, activity, {"selected": activity.solution["correct"]})

    assert at_once(db.get_bind(), answer) == []
    assert db.scalar(select(func.count(Attempt.id))) == TIMES


def test_the_same_right_answer_twice_at_once_earns_its_points_once(db: Session) -> None:
    load(db)
    user_id = student(db)
    activity_id = db.scalars(select(Activity.id).where(Activity.module_id == 0)).first()

    def answer(session: Session) -> None:
        activity = session.get_one(Activity, activity_id)
        record_attempt(session, user_id, activity, {"selected": activity.solution["correct"]})

    assert at_once(db.get_bind(), answer) == []
    assert db.scalar(select(func.count(Attempt.id))) == TIMES
    assert db.scalar(select(func.count(PointsEntry.id))) == 1


def test_a_double_clicked_first_next_saves_once(db: Session) -> None:
    load(db)
    user_id = student(db)

    def save(session: Session) -> None:
        save_position(session, user_id, 0, 1)

    assert at_once(db.get_bind(), save) == []
    rows = db.scalars(select(ModuleProgress).where(ModuleProgress.user_id == user_id)).all()
    assert [(r.module_id, r.current_segment_position) for r in rows] == [(0, 1)]


def test_hint_requests_at_once_reveal_each_level_once(db: Session) -> None:
    load(db)
    user_id = student(db)
    activity_id = db.scalars(select(Activity.id).where(Activity.module_id == 0)).first()

    def reveal(session: Session) -> None:
        reveal_next_hint(session, user_id, session.get_one(Activity, activity_id))

    assert at_once(db.get_bind(), reveal) == []
    levels = db.scalars(select(HintView.level).where(HintView.user_id == user_id)).all()
    assert sorted(levels) == sorted(set(levels))  # no level twice
