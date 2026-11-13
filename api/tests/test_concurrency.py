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
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker
from support import complete_modules_before

from app.main import app as fastapi_app
from app.models import (
    Activity,
    Attempt,
    Event,
    Hint,
    HintView,
    Module,
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
    assert db.scalar(select(func.count()).where(ObjectiveResult.user_id == user_id)) == 8


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


def test_a_request_queued_behind_the_accounts_deletion_is_401(
    client: TestClient, committed: Session
) -> None:
    """The student's answer arrives while staff are deleting the account: it waits for the
    student's lock, finds no student when it gets it, and answers 401 as any later request
    would, instead of failing on the foreign key (409)."""
    from app.services.history import delete_history
    from app.services.locks import lock_student

    db = committed
    assert client.post("/api/auth/register", json=STUDENT).status_code == 201
    me = user_id(db)
    engine = db.get_bind()
    assert isinstance(engine, Engine)
    status: list[int] = []
    with Session(engine) as deleting:  # what DELETE /api/staff/accounts/{id} does, held open
        lock_student(deleting, me)
        delete_history(deleting, me)
        deleting.delete(deleting.get_one(User, me))
        deleting.flush()
        thread = threading.Thread(
            target=lambda: status.append(
                client.post(
                    "/api/activities/1/attempts", json={"submitted": right(db, 1)}
                ).status_code
            )
        )
        thread.start()
        thread.join(timeout=WAIT)
        assert thread.is_alive(), "the answer should wait for the deletion"
        deleting.commit()
        thread.join(timeout=20)
    assert status == [401]
    db.expire_all()
    assert db.scalar(select(func.count()).where(Attempt.user_id == me)) == 0


def test_an_answer_to_an_activity_the_seed_is_deleting_does_not_deadlock(
    committed: Session,
) -> None:
    """On a deploy the seed deletes unused activities, then recomputes students. An answer to one
    of them used to take the student's lock first and then wait for the activity, while the seed
    held the activity and waited for the student. Now the answer waits for the activity first,
    holding nothing, and finds it gone."""
    from sqlalchemy import delete

    from app.services.locks import ActivityGone

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


def test_the_seed_waits_for_an_answer_already_being_recorded(committed: Session) -> None:
    """The other order: the answer takes its locks and inserts its attempt first, then the seed's
    retire_dropped_activities reaches that activity. The seed used to see no committed use,
    delete it, wait, and then fail on the foreign key. Now it locks the activity first, waits
    for the answer, sees the attempt and only hides the activity (#138)."""
    from app.seed import read_fixtures, retire_dropped_activities

    db = committed
    user_id = student(db)
    engine = db.get_bind()
    assert isinstance(engine, Engine)
    dropped = Activity(
        id=9003,
        kind="multiple_choice",
        title="Dropped from the fixtures",
        module_id=0,
        visible=True,
        config={"prompt": "Q", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]},
        solution={"correct": "a"},
    )
    db.add(dropped)
    db.commit()
    listed = {a.id for a in read_fixtures().activities}
    with Session(engine) as answering:
        record_attempt(answering, user_id, answering.get_one(Activity, 9003), {"selected": "a"})
        answering.flush()
        racer = Racer(engine, lambda s: retire_dropped_activities(s, listed))
        racer.thread.join(timeout=WAIT)
        assert racer.thread.is_alive(), "the seed should wait for the answer"
        answering.commit()
        racer.join()  # staging and 7da26f6: ForeignKeyViolation
    assert 9003 in racer.result
    db.expire_all()
    kept = db.get_one(Activity, 9003)
    assert (kept.visible, kept.module_id) == (False, None)
    assert db.scalar(select(func.count()).where(Attempt.activity_id == 9003)) == 1


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
    # Every one was right, but the check isn't finished, so no item has paid yet (#144); none
    # failed on a duplicate either.
    paid = db.scalars(select(PointsEntry.ref).where(PointsEntry.user_id == me)).all()
    assert not {f"activity:{i}" for i in items} & set(paid)
    assert len(paid) == len(set(paid))


def test_a_burst_of_one_mastery_answer_records_it_once(
    clients: list[TestClient], committed: Session
) -> None:
    """The mastery check's one answer is checked under the student's lock (#144): ten sent at
    once record one and refuse the rest."""
    db = committed
    complete_modules_before(db, STUDENT["email"], 6)
    item = db.scalars(
        select(Activity.id)
        .where(Activity.module_id == 6, Activity.kind == "multiple_choice")
        .order_by(Activity.id)
    ).first()
    assert item is not None
    answer = {"submitted": right(db, item)}
    responses = burst(
        clients, lambda tab, _: tab.post(f"/api/activities/{item}/attempts", json=answer)
    )
    assert Counter(r.status_code for r in responses) == {201: 1, 409: 9}
    db.expire_all()
    me = user_id(db)
    assert db.scalar(select(func.count()).where(Attempt.user_id == me)) == 1


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


# --- Many identical writes at the same moment, straight through the services (#163) -----------

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
