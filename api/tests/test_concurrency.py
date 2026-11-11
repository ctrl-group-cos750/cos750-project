"""One student's writes at the same moment (#138; FR-2.5, FR-4.4, FR-7, FR-9).

Postgres only: SQLite has no row locks, so it can't show these races. Each test runs the writes in
separate threads, each with its own session and database connection, so they really overlap.

Two kinds of test. The first kind fixes the interleaving that used to fail: one transaction
stops half-way, holding its locks, while the other runs, so each would fail every time on staging
(e8973c5). The second kind fires a burst of real HTTP requests at once, a double-click or a
script, and checks every request succeeded and the database holds what one request at a time
would have left.
"""

import os
import threading
from collections import Counter
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session
from support import complete_modules_before

from app.main import app as fastapi_app
from app.models import (
    Activity,
    Attempt,
    Event,
    Hint,
    HintView,
    ModuleProgress,
    ObjectiveResult,
    PointsEntry,
    User,
)
from app.seed import load
from app.services import mastery
from app.services.attempts import record_attempt, reveal_next_hint
from app.services.modules import save_position

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="needs Postgres row locks"
)

STUDENT = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}
WAIT = 1.5  # long enough for a blocked transaction to show it is blocked


@pytest.fixture
def committed(db: Session) -> Session:
    load(db)
    return db


def student(db: Session) -> int:
    user = User(email="z@example.com", display_name="Z", password_hash="x")  # noqa: S106
    db.add(user)
    db.commit()
    return user.id


class Racer:
    """Runs `work(session)` in its own thread, session and connection, then commits."""

    def __init__(self, engine: Engine, work: Callable[[Session], Any]) -> None:
        self.error: BaseException | None = None
        self.result: Any = None

        def run() -> None:
            try:
                with Session(engine) as session:
                    self.result = work(session)
                    session.commit()
            except BaseException as exc:  # reported by the test, from its own thread
                self.error = exc

        self.thread = threading.Thread(target=run)
        self.thread.start()

    def join(self) -> None:
        self.thread.join(timeout=20)
        assert not self.thread.is_alive(), "still blocked: a lock was never released"
        if self.error is not None:
            raise self.error


# --- The interleavings that failed on staging ---------------------------------------------------


def test_two_mastery_answers_inserted_before_either_recomputes_do_not_deadlock(
    committed: Session,
) -> None:
    """The deadlock in #138: both transactions insert their attempt (each takes KEY SHARE on the
    student's row), then each recomputes. A plain FOR UPDATE there waits for the other's KEY
    SHARE, so Postgres killed one with DeadlockDetected and its answer was lost (a 500)."""
    db = committed
    user_id = student(db)
    engine = db.get_bind()
    assert isinstance(engine, Engine)
    with Session(engine) as first, Session(engine) as second:
        first.add(Attempt(user_id=user_id, activity_id=601, submitted={}, correct=True,
                          score=1, detail={}))  # fmt: skip
        first.flush()
        second.add(Attempt(user_id=user_id, activity_id=606, submitted={}, correct=True,
                           score=1, detail={}))  # fmt: skip
        second.flush()
        # The second recomputes in another thread while the first holds its insert's lock.
        errors: list[BaseException] = []

        def recompute_second() -> None:
            try:
                mastery.recompute(second, user_id)
                second.commit()
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=recompute_second)
        thread.start()
        thread.join(timeout=WAIT)
        mastery.recompute(first, user_id)  # staging: deadlock, one of the two is killed
        first.commit()
        thread.join(timeout=20)
        assert not thread.is_alive()
        assert errors == []
    db.expire_all()
    assert db.scalar(select(func.count()).where(Attempt.user_id == user_id)) == 2
    assert db.scalar(select(func.count()).where(ObjectiveResult.user_id == user_id)) == 7


def test_a_second_answer_waits_for_the_first_then_sees_its_points(committed: Session) -> None:
    """Two correct answers to one activity at once: the first earns its 10 points; the second
    used to find no points row yet, insert one too and fail on the unique (user, ref) (500)."""
    db = committed
    user_id = student(db)
    engine = db.get_bind()
    assert isinstance(engine, Engine)
    answer = right(db, 1)
    with Session(engine) as first:
        record_attempt(first, user_id, first.get_one(Activity, 1), answer)
        racer = Racer(engine, lambda s: record_attempt(s, user_id, s.get_one(Activity, 1), answer))
        racer.thread.join(timeout=WAIT)
        assert racer.thread.is_alive(), "the second answer should wait for the first's lock"
        first.commit()
        racer.join()
    db.expire_all()
    points = db.scalars(select(PointsEntry.points).where(PointsEntry.user_id == user_id)).all()
    assert points == [10]
    assert db.scalar(select(func.count()).where(Attempt.user_id == user_id)) == 2


def test_two_first_position_saves_at_once_make_one_progress_row(committed: Session) -> None:
    """The double-clicked first "Next" in #138: both saves found no progress row, both inserted
    one, and the second failed on the unique (user, module) (500)."""
    db = committed
    user_id = student(db)
    engine = db.get_bind()
    assert isinstance(engine, Engine)
    with Session(engine) as first:
        save_position(first, user_id, 0, 1)
        racer = Racer(engine, lambda s: save_position(s, user_id, 0, 1))
        racer.thread.join(timeout=WAIT)
        assert racer.thread.is_alive(), "the second save should wait for the first's lock"
        first.commit()
        racer.join()  # staging: IntegrityError (UniqueViolation)
    db.expire_all()
    rows = db.scalars(select(ModuleProgress).where(ModuleProgress.user_id == user_id)).all()
    assert [(r.module_id, r.current_segment_position) for r in rows] == [(0, 1)]


def test_two_hint_requests_at_once_reveal_two_levels(committed: Session) -> None:
    """Both requests used to read "level 0 seen" and reveal level 1, so the pilot's hint counts
    (FR-10) showed six views for a four-level ladder."""
    db = committed
    user_id = student(db)
    engine = db.get_bind()
    assert isinstance(engine, Engine)
    with Session(engine) as first:
        shown = reveal_next_hint(first, user_id, first.get_one(Activity, 1))
        assert shown is not None
        assert shown[0].level == 1

        def second(s: Session) -> int | None:
            revealed = reveal_next_hint(s, user_id, s.get_one(Activity, 1))
            return revealed[0].level if revealed else None

        racer = Racer(engine, second)
        racer.thread.join(timeout=WAIT)
        assert racer.thread.is_alive(), "the second request should wait for the first's lock"
        first.commit()
        racer.join()
    assert racer.result == 2
    db.expire_all()
    levels = db.scalars(select(HintView.level).where(HintView.user_id == user_id)).all()
    assert sorted(levels) == [1, 2]


def test_deleting_an_account_waits_for_its_answer_in_flight(
    client: TestClient, committed: Session
) -> None:
    """Staff delete an account (DELETE /api/staff/accounts/{id}) while the student's answer is
    being recorded: the deletion waits for it, then removes it with the rest. It used to delete
    the history first, miss the answer still uncommitted, and fail on the foreign key (500)."""
    db = committed
    user_id = student(db)
    assert client.post("/api/auth/register", json=STUDENT).status_code == 201
    db.get_one(User, user_id_of(db, STUDENT["email"])).is_staff = True
    db.commit()
    engine = db.get_bind()
    assert isinstance(engine, Engine)
    status: list[int] = []
    with Session(engine) as answering:
        record_attempt(answering, user_id, answering.get_one(Activity, 1), right(db, 1))
        thread = threading.Thread(
            target=lambda: status.append(
                client.delete(f"/api/staff/accounts/{user_id}").status_code
            )
        )
        thread.start()
        thread.join(timeout=WAIT)
        assert thread.is_alive(), "the deletion should wait for the answer"
        answering.commit()
        thread.join(timeout=20)
    assert status == [204]
    db.expire_all()
    assert db.get(User, user_id) is None
    assert db.scalar(select(func.count()).where(Attempt.user_id == user_id)) == 0


def test_an_answer_to_an_activity_the_seed_is_deleting_does_not_deadlock(
    committed: Session,
) -> None:
    """On a deploy the seed deletes unused activities, then recomputes students. An answer to one
    of them used to take the student's lock first and then wait for the activity, while the seed
    held the activity and waited for the student. Now the answer waits for the activity first,
    holding nothing, and finds it gone."""
    from sqlalchemy import delete

    from app.services.locking import ActivityGone

    db = committed
    user_id = student(db)
    engine = db.get_bind()
    assert isinstance(engine, Engine)
    doomed = Activity(
        kind="multiple_choice",
        title="Dropped",
        module_id=0,
        config={"prompt": "Q", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]},
        solution={"correct": "a"},
    )
    db.add(doomed)
    db.commit()
    with Session(engine) as seed:
        seed.execute(delete(Activity).where(Activity.id == doomed.id))  # retire_dropped_activities
        seed.flush()
        racer = Racer(
            engine,
            lambda s: record_attempt(s, user_id, s.get_one(Activity, doomed.id), {"selected": "a"}),
        )
        racer.thread.join(timeout=WAIT)
        assert racer.thread.is_alive(), "the answer should wait for the activity"
        mastery.recompute(seed, user_id)  # recompute_all; staging deadlocked here
        seed.commit()
        with pytest.raises(ActivityGone):
            racer.join()
    db.expire_all()
    assert db.scalar(select(func.count()).where(Attempt.user_id == user_id)) == 0


def test_one_students_lock_never_holds_up_another(committed: Session) -> None:
    db = committed
    ada = student(db)
    other = User(email="y@example.com", display_name="Y", password_hash="x")  # noqa: S106
    db.add(other)
    db.commit()
    engine = db.get_bind()
    assert isinstance(engine, Engine)
    with Session(engine) as first:
        save_position(first, ada, 0, 1)
        racer = Racer(engine, lambda s: save_position(s, other.id, 0, 1))
        racer.join()  # finishes while Ada's transaction is still open
        first.commit()


# --- Bursts of real requests --------------------------------------------------------------------


def right(db: Session, activity_id: int) -> dict[str, Any]:
    activity = db.get_one(Activity, activity_id)
    assert activity.kind == "multiple_choice"
    return {"selected": activity.solution["correct"]}


@pytest.fixture
def clients(client: TestClient, committed: Session) -> Iterator[list[TestClient]]:
    """Ten browser tabs signed in as one student."""
    assert client.post("/api/auth/register", json=STUDENT).status_code == 201
    tabs = [
        TestClient(fastapi_app, base_url="https://testserver", cookies=client.cookies)
        for _ in range(10)
    ]
    for tab in tabs:
        tab.__enter__()
    yield tabs
    for tab in tabs:
        tab.__exit__(None, None, None)


def burst(tabs: list[TestClient], send: Callable[[TestClient, int], Any]) -> list[Any]:
    """Every tab sends at the same moment; the responses, in tab order."""
    start = threading.Barrier(len(tabs))
    out: list[Any] = [None] * len(tabs)

    def run(i: int) -> None:
        start.wait()
        out[i] = send(tabs[i], i)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(len(tabs))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return out


def user_id_of(db: Session, email: str) -> int:
    return db.scalars(select(User.id).where(User.email == email)).one()


def user_id(db: Session) -> int:
    return user_id_of(db, STUDENT["email"])


def test_a_burst_of_mastery_answers_all_record(
    clients: list[TestClient], committed: Session
) -> None:
    """Ten module 6 answers at once (the analysis saw 4 in 10 lost to the deadlock)."""
    db = committed
    complete_modules_before(db, STUDENT["email"], 6)
    items = db.scalars(
        select(Activity.id)
        .where(Activity.module_id == 6, Activity.kind == "multiple_choice")
        .order_by(Activity.id)
    ).all()[:10]
    answers = {i: right(db, i) for i in items}
    responses = burst(
        clients,
        lambda tab, i: tab.post(
            f"/api/activities/{items[i]}/attempts", json={"submitted": answers[items[i]]}
        ),
    )
    assert Counter(r.status_code for r in responses) == {201: 10}
    db.expire_all()
    me = user_id(db)
    assert db.scalar(select(func.count()).where(Attempt.user_id == me)) == 10
    # Every one was right, so each earned its activity's points, and none failed on a duplicate.
    paid = db.scalars(select(PointsEntry.ref).where(PointsEntry.user_id == me)).all()
    assert {f"activity:{i}" for i in items} <= set(paid)
    assert len(paid) == len(set(paid))


def test_a_burst_of_the_same_correct_answer_pays_once(
    clients: list[TestClient], committed: Session
) -> None:
    db = committed
    answer = {"submitted": right(db, 1)}
    responses = burst(clients, lambda tab, _: tab.post("/api/activities/1/attempts", json=answer))
    assert Counter(r.status_code for r in responses) == {201: 10}
    db.expire_all()
    me = user_id(db)
    assert db.scalars(select(PointsEntry.points).where(PointsEntry.user_id == me)).all() == [10]


def test_a_burst_of_first_position_saves_all_succeed(
    clients: list[TestClient], committed: Session
) -> None:
    """The analysis saw 9 in 10 fail with 500."""
    responses = burst(
        clients, lambda tab, _: tab.post("/api/modules/0/position", json={"segmentPosition": 1})
    )
    assert Counter(r.status_code for r in responses) == {200: 10}
    db = committed
    db.expire_all()
    rows = db.scalars(select(ModuleProgress).where(ModuleProgress.user_id == user_id(db))).all()
    assert [(r.module_id, r.current_segment_position) for r in rows] == [(0, 1)]


def test_a_burst_of_hint_requests_reveals_each_level_once(
    clients: list[TestClient], committed: Session
) -> None:
    """Ten requests on a four-level ladder: four reveal a level each, in order, and six are told
    there are no more. The analysis saw six views stored for four levels."""
    db = committed
    ladder = db.scalars(select(Hint.level).where(Hint.activity_id == 1)).all()
    assert sorted(ladder) == [1, 2, 3, 4]
    responses = burst(clients, lambda tab, _: tab.post("/api/activities/1/hints"))
    assert Counter(r.status_code for r in responses) == {201: 4, 409: 6}
    assert sorted(r.json()["level"] for r in responses if r.status_code == 201) == [1, 2, 3, 4]
    db.expire_all()
    me = user_id(db)
    assert sorted(db.scalars(select(HintView.level).where(HintView.user_id == me))) == [1, 2, 3, 4]
    shown = db.scalar(select(func.count()).where(Event.user_id == me, Event.type == "hint_shown"))
    assert shown == 4
