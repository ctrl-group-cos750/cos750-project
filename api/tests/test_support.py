"""Support segments for a struggling student (FR-8.4, #172; app/services/support.py).

A module's support segments for an objective are shown only to a student struggling with that
objective in that module: 2 of the last 3 first attempts at its base practice items wrong, or one
made after hint 3 or 4. They stay in the list for everyone, so positions never shift; a hidden one
counts as done and is skipped. Once shown, support stays shown.
"""

import os
import threading
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    Activity,
    Attempt,
    Hint,
    Module,
    ModuleProgress,
    Objective,
    Segment,
    ShownSegment,
    User,
)
from app.services import support
from app.services.attempts import record_attempt
from app.services.modules import get_module_detail, save_position
from app.services.support import FirstAttempt, struggling

ADA = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}
BEA = {"email": "bea@example.com", "password": "Correct horse 2", "displayName": "Bea"}

# Module 0's segments, by position. 1-3 are base practice on objective 2, 4-5 its support, then a
# closing text. Activity 14 is base practice on objective 2 too, placed after the support (only in
# the tests that add it).
INTRO, BASE_1, BASE_2, BASE_3, SUPPORT_TEXT, SUPPORT_ITEM, CLOSING = range(7)


def W(hint: int = 0) -> FirstAttempt:
    return FirstAttempt(correct=False, hint_level=hint)


def R(hint: int = 0) -> FirstAttempt:
    return FirstAttempt(correct=True, hint_level=hint)


# --- The rule ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("attempts", "expected"),
    [
        ([], False),  # nothing answered yet: not yet
        ([W()], False),  # one wrong answer is not enough to say
        ([R(), R(), R()], False),
        ([W(), W()], True),  # 2 of the (only) 2
        ([W(), R(), W()], True),  # 2 of the last 3
        ([R(), W(), R(), R(), W()], False),  # never 2 wrong within 3 in a row
        ([W(), R(), R(), W()], False),
        ([R(), R(), W(), W()], True),
        ([W(), W(), R(), R(), R()], True),  # it was true once, so it stays true
        ([R(2), R(2)], False),  # hints 1 and 2 are nudges, not the answer
        ([R(3)], True),  # needed hint 3
        ([R(), R(4)], True),  # needed hint 4, even though right
        ([W(), R(), R(), R(3)], True),
    ],
)
def test_the_rule(attempts: list[FirstAttempt], expected: bool) -> None:
    assert struggling(attempts) is expected


def test_the_rule_is_tuned_by_its_constants(monkeypatch: pytest.MonkeyPatch) -> None:
    assert struggling([W(), R(), R(), W()]) is False
    monkeypatch.setattr(support, "WINDOW", 4)
    assert struggling([W(), R(), R(), W()]) is True
    monkeypatch.setattr(support, "HINT_TO_STRUGGLE", 5)
    assert struggling([R(4)]) is False


# --- A module with support ---------------------------------------------------------------------


def _question(db: Session, activity_id: int, **tags: Any) -> None:
    db.add(
        Activity(
            id=activity_id,
            kind="multiple_choice",
            title=f"Question {activity_id}",
            config={
                "prompt": "Which?",
                "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            },
            solution={"correct": "a", "feedback": {}},
            **tags,
        )
    )
    db.flush()
    for level in (1, 2, 3, 4):
        db.add(Hint(activity_id=activity_id, level=level, body=f"Hint {level}."))


def _make_module(db: Session, *, closing: bool = True, late_base: bool = False) -> None:
    """Module 0: an intro, three base practice items on objective 2, its support (a worked example
    and a fresh item), and a closing text. Module 1 after it."""
    for objective in (1, 2):
        db.add(Objective(id=objective, text="o", bloom_level="Apply", criterion="c", max_wrong=1))
    db.add_all(
        [
            Module(id=0, slug="m0", title="Zero", goals=[], estimated_minutes=10, position=0),
            Module(id=1, slug="m1", title="One", goals=[], estimated_minutes=10, position=1),
        ]
    )
    db.flush()
    practice = {"module_id": 0, "objective_id": 2, "purpose": "practice"}
    for activity_id in (11, 12, 13, 19):
        _question(db, activity_id, **practice)
    _question(db, 20, module_id=0, objective_id=1, purpose="practice")  # another objective
    segments = [
        Segment(id=1, kind="text", title="Intro", body="Text."),
        Segment(id=2, kind="activity", title="Base 1", activity_id=11),
        Segment(id=3, kind="activity", title="Base 2", activity_id=12),
        Segment(id=4, kind="activity", title="Base 3", activity_id=13),
        Segment(id=90, kind="text", title="Another way", body="Example.", support_for=2),
        Segment(id=91, kind="activity", title="Try again", activity_id=19, support_for=2),
    ]
    if late_base:
        _question(db, 14, **practice)
        segments.append(Segment(id=5, kind="activity", title="Base 4", activity_id=14))
    if closing:
        segments.append(Segment(id=6, kind="text", title="Closing", body="Text."))
    for position, segment in enumerate(segments):
        segment.module_id = 0
        segment.position = position
    db.add_all(segments)
    db.add(Segment(id=100, module_id=1, position=0, kind="text", title="Next", body="Text."))
    db.commit()


def _register(client: TestClient, user: dict[str, str]) -> None:
    assert client.post("/api/auth/register", json=user).status_code == 201


def _answer(client: TestClient, activity_id: int, right: bool) -> None:
    res = client.post(
        f"/api/activities/{activity_id}/attempts",
        json={"submitted": {"selected": "a" if right else "b"}},
    )
    assert res.status_code in (200, 201), res.text


def _hints(client: TestClient, activity_id: int, levels: int) -> None:
    for _ in range(levels):
        assert client.post(f"/api/activities/{activity_id}/hints").status_code == 201


def _move(client: TestClient, position: int) -> int:
    return client.post("/api/modules/0/position", json={"segmentPosition": position}).status_code


def _detail(client: TestClient) -> dict[str, Any]:
    res = client.get("/api/modules/0")
    assert res.status_code == 200
    return res.json()


def _shown(client: TestClient) -> list[bool]:
    return [s["shown"] for s in _detail(client)["segments"]]


def _summary(client: TestClient) -> dict[str, Any]:
    return next(m for m in client.get("/api/modules").json() if m["id"] == 0)


def _walk_base(client: TestClient, answers: tuple[bool, bool, bool]) -> None:
    """Answer the three base items in order, moving onto each, and end on the third."""
    for position, (activity_id, right) in enumerate(zip((11, 12, 13), answers, strict=True), 1):
        assert _move(client, position) == 200
        _answer(client, activity_id, right)


def test_a_confident_student_never_sees_the_support(client: TestClient, db: Session) -> None:
    _make_module(db)
    _register(client, ADA)
    _walk_base(client, (True, True, False))  # one slip is not struggling

    detail = _detail(client)
    assert [s["shown"] for s in detail["segments"]] == [True, True, True, True, False, False, True]
    assert [s["supportFor"] for s in detail["segments"]] == [None, None, None, None, 2, 2, None]
    hidden = [s for s in detail["segments"] if not s["shown"]]
    assert all(s["done"] for s in hidden)  # hidden support counts as done
    assert detail["segmentCount"] == 7  # every segment stays in the list: positions never shift
    assert detail["shownSegmentCount"] == 5
    # Next goes straight from the last base item past the support to the closing text.
    assert _move(client, SUPPORT_TEXT) == 409  # not onto support they aren't shown
    assert _move(client, CLOSING) == 200
    detail = _detail(client)
    assert detail["currentSegmentPosition"] == CLOSING
    assert detail["shownSegmentsPassed"] == 4  # intro and the three base items
    assert _move(client, CLOSING) == 200  # Finish module
    assert _summary(client)["status"] == "complete"
    assert db.scalars(select(ShownSegment)).all() == []


def test_a_struggling_student_gets_the_support_next(client: TestClient, db: Session) -> None:
    _make_module(db)
    _register(client, ADA)
    assert _move(client, BASE_1) == 200
    _answer(client, 11, False)
    assert _shown(client)[SUPPORT_TEXT] is False  # one wrong answer: not yet
    assert _move(client, BASE_2) == 200
    _answer(client, 12, False)
    # 2 of the last 3 wrong: the support is shown, ahead of them, before they get there.
    assert _shown(client) == [True] * 7
    assert _detail(client)["shownSegmentCount"] == 7
    assert _move(client, BASE_3) == 200
    _answer(client, 13, True)
    assert _move(client, CLOSING) == 409  # the support is in the way now
    assert _move(client, SUPPORT_TEXT) == 200
    assert _move(client, SUPPORT_ITEM) == 200
    assert _move(client, CLOSING) == 409  # a shown support item follows the done rule (FR-2.7)
    _answer(client, 19, True)
    assert _move(client, CLOSING) == 200
    assert _move(client, CLOSING) == 200
    assert _summary(client)["status"] == "complete"
    assert _summary(client)["shownSegmentCount"] == 7


def test_a_first_attempt_after_hint_3_is_struggling(client: TestClient, db: Session) -> None:
    _make_module(db)
    _register(client, ADA)
    assert _move(client, BASE_1) == 200
    _hints(client, 11, 2)
    _answer(client, 11, True)
    assert _shown(client)[SUPPORT_TEXT] is False  # hint 2 is not enough
    assert _move(client, BASE_2) == 200
    _hints(client, 12, 3)
    _answer(client, 12, True)
    assert _shown(client)[SUPPORT_TEXT] is True


def test_only_first_attempts_at_base_practice_here_count(client: TestClient, db: Session) -> None:
    _make_module(db)
    db.add_all(
        [
            Activity(  # a retrieval question on the same objective, in the same module
                id=30,
                kind="multiple_choice",
                title="Recall",
                config={
                    "prompt": "?",
                    "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                },
                solution={"correct": "a", "feedback": {}},
                module_id=0,
                objective_id=2,
                purpose="retrieval",
            ),
        ]
    )
    db.commit()
    _register(client, ADA)
    _answer(client, 30, False)  # a wrong retrieval answer is no evidence here
    assert _move(client, BASE_1) == 200
    _answer(client, 11, True)
    _answer(client, 11, False)  # a later attempt at the same item doesn't count
    _answer(client, 11, False)
    _answer(client, 20, False)  # another objective's item doesn't count for objective 2
    _answer(client, 19, False)  # nor does the support item itself
    assert _shown(client)[SUPPORT_TEXT] is False


def test_once_shown_support_stays_shown(client: TestClient, db: Session) -> None:
    _make_module(db)
    _register(client, ADA)
    _walk_base(client, (False, False, True))
    assert _move(client, SUPPORT_TEXT) == 200  # moving onto it records it
    user_id = db.scalar(select(User.id).where(User.email == ADA["email"]))
    assert {r.segment_id for r in db.scalars(select(ShownSegment))} == {90, 91}
    # A re-grade turns the wrong answers right: the rule would now say no, but it stays shown.
    db.execute(update(Attempt).where(Attempt.user_id == user_id).values(correct=True))
    db.commit()
    assert _shown(client) == [True] * 7
    assert _move(client, SUPPORT_ITEM) == 200
    assert _move(client, CLOSING) == 409


def test_support_shown_ahead_is_recorded_by_the_next_save(client: TestClient, db: Session) -> None:
    _make_module(db)
    _register(client, ADA)
    assert _move(client, BASE_1) == 200
    _answer(client, 11, False)
    assert _move(client, BASE_2) == 200
    _answer(client, 12, False)
    assert _move(client, BASE_3) == 200  # support shown at this save: recorded
    assert {r.segment_id for r in db.scalars(select(ShownSegment))} == {90, 91}
    db.execute(update(Attempt).values(correct=True))  # re-graded before they reach it
    db.commit()
    assert _shown(client)[SUPPORT_TEXT] is True


def test_support_is_never_shown_behind_the_student(client: TestClient, db: Session) -> None:
    """The rule fires only after the student has passed the support (evidence from a base item
    placed later): it is not shown behind them, and not inserted ahead of them either."""
    _make_module(db, late_base=True)  # base item 14 at position 6, after the support
    _register(client, ADA)
    _walk_base(client, (True, True, True))
    assert _move(client, 6) == 200  # past the hidden support, onto base item 14
    _hints(client, 14, 4)
    _answer(client, 14, True)  # needed hint 4: struggling now
    detail = _detail(client)
    assert [s["shown"] for s in detail["segments"]][SUPPORT_TEXT : SUPPORT_ITEM + 1] == [
        False,
        False,
    ]
    assert detail["currentSegmentPosition"] == 6
    assert _move(client, 7) == 200
    assert _move(client, 7) == 200
    assert _summary(client)["status"] == "complete"


def test_a_complete_module_never_gains_support(client: TestClient, db: Session) -> None:
    _make_module(db)
    _register(client, ADA)
    _walk_base(client, (True, True, True))
    assert _move(client, CLOSING) == 200
    assert _move(client, CLOSING) == 200
    db.execute(update(Attempt).values(correct=False))  # whatever happens to the evidence later
    db.commit()
    assert _shown(client)[SUPPORT_TEXT] is False
    assert _summary(client)["status"] == "complete"


def test_hidden_support_at_the_end_doesnt_hold_up_completion(
    client: TestClient, db: Session
) -> None:
    _make_module(db, closing=False)  # the support is the module's last two segments
    _register(client, ADA)
    _walk_base(client, (True, True, True))
    assert _move(client, SUPPORT_TEXT) == 409
    assert _move(client, BASE_3) == 200  # "Finish module" on the last segment shown
    assert _summary(client)["status"] == "complete"
    assert _summary(client)["shownSegmentCount"] == 4


def test_shown_support_at_the_end_has_to_be_done(client: TestClient, db: Session) -> None:
    _make_module(db, closing=False)
    _register(client, ADA)
    _walk_base(client, (False, False, True))
    assert _move(client, BASE_3) == 200
    assert _summary(client)["status"] == "in_progress"
    assert _move(client, SUPPORT_TEXT) == 200
    assert _move(client, SUPPORT_ITEM) == 200
    assert _summary(client)["status"] == "in_progress"  # its item isn't answered yet
    _answer(client, 19, True)
    assert _move(client, SUPPORT_ITEM) == 200
    assert _summary(client)["status"] == "complete"


def test_two_students_see_only_what_each_needs(client: TestClient, db: Session) -> None:
    _make_module(db)
    _register(client, ADA)
    _walk_base(client, (False, False, False))
    client.post("/api/auth/logout")
    _register(client, BEA)
    _walk_base(client, (True, True, True))
    assert _shown(client)[SUPPORT_TEXT] is False
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": ADA["email"], "password": ADA["password"]})
    assert _shown(client)[SUPPORT_TEXT] is True


def test_the_map_counts_only_the_segments_shown(client: TestClient, db: Session) -> None:
    _make_module(db)
    _register(client, ADA)
    before = _summary(client)  # no progress row yet
    assert (before["segmentCount"], before["shownSegmentCount"]) == (7, 5)
    assert before["shownSegmentsPassed"] == 0
    _walk_base(client, (True, True, True))
    assert _move(client, CLOSING) == 200
    after = _summary(client)
    assert after["currentSegmentPosition"] == CLOSING
    assert (after["shownSegmentCount"], after["shownSegmentsPassed"]) == (5, 4)


def test_junk_positions_are_still_refused(client: TestClient, db: Session) -> None:
    _make_module(db)
    _register(client, ADA)
    _walk_base(client, (True, True, True))
    for junk in (99, 10**9, SUPPORT_ITEM):
        assert _move(client, junk) == 409
    assert client.post("/api/modules/0/position", json={"segmentPosition": -1}).status_code == 422
    assert client.post("/api/modules/0/position", json={"segmentPosition": "x"}).status_code == 422
    assert _detail(client)["currentSegmentPosition"] == BASE_3


def test_a_module_without_support_is_unchanged(client: TestClient, db: Session) -> None:
    _make_module(db)
    _register(client, ADA)
    one = client.get("/api/modules/1")
    assert one.status_code == 403  # still locked; the rest of the map is as before
    m1 = next(m for m in client.get("/api/modules").json() if m["id"] == 1)
    assert (m1["segmentCount"], m1["shownSegmentCount"], m1["shownSegmentsPassed"]) == (1, 1, 0)


# --- Two first attempts at once, on Postgres ---------------------------------------------------

postgres = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="needs Postgres (TEST_DATABASE_URL)"
)


def _at_once(db: Session, actions: list[Callable[[Session], Any]]) -> list[BaseException]:
    sessions = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    start = threading.Barrier(len(actions))
    errors: list[BaseException] = []

    def run(action: Callable[[Session], Any]) -> None:
        with sessions() as session:
            start.wait()
            try:
                action(session)
                session.commit()
            except BaseException as exc:
                session.rollback()
                errors.append(exc)

    threads = [threading.Thread(target=run, args=(a,)) for a in actions]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return errors


def _student(db: Session) -> int:
    user = User(email="ada@example.com", display_name="Ada", password_hash="x")  # noqa: S106 (test only)
    db.add(user)
    db.commit()
    db.add(ModuleProgress(user_id=user.id, module_id=0, status="in_progress"))
    db.commit()
    return user.id


def _wrong(user_id: int, activity_id: int) -> Callable[[Session], Any]:
    def answer(session: Session) -> None:
        activity = session.get_one(Activity, activity_id)
        record_attempt(session, user_id, activity, {"selected": "b"})

    return answer


@postgres
def test_two_first_attempts_at_once_both_count(db: Session) -> None:
    _make_module(db)
    user_id = _student(db)
    assert _at_once(db, [_wrong(user_id, 11), _wrong(user_id, 12)]) == []
    db.expire_all()
    shown = [s.shown for s in get_module_detail(db, user_id, 0).segments]
    assert shown[SUPPORT_TEXT]
    assert shown[SUPPORT_ITEM]


@postgres
def test_saves_at_once_record_the_support_once(db: Session) -> None:
    _make_module(db)
    user_id = _student(db)
    for activity_id in (11, 12, 13):
        record_attempt(db, user_id, db.get_one(Activity, activity_id), {"selected": "b"})
    db.execute(
        update(ModuleProgress)
        .where(ModuleProgress.user_id == user_id)
        .values(current_segment_position=BASE_3)
    )
    db.commit()

    def move(session: Session) -> None:
        save_position(session, user_id, 0, SUPPORT_TEXT)

    assert _at_once(db, [move] * 6) == []
    db.expire_all()
    rows = db.scalars(select(ShownSegment).where(ShownSegment.user_id == user_id)).all()
    assert sorted(r.segment_id for r in rows) == [90, 91]
    progress = db.scalars(select(ModuleProgress).where(ModuleProgress.user_id == user_id)).one()
    assert progress.current_segment_position == SUPPORT_TEXT
