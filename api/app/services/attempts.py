"""Recording a student's attempts and hint views (FR-4.2, FR-4.4, FR-4.5, FR-5.3).

The activity routes call these, and so does the demo-account seed (app/seed/demo_accounts.py), so
a demo account's history is graded and recorded exactly as a real student's would be.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Hint, HintView, Segment
from app.schemas.activities import CheckResult
from app.services.checking import check_activity, is_blank
from app.services.events import log_event
from app.services.locks import hold_activity, lock_student
from app.services.mastery import counts, in_check, recompute
from app.services.modules import reward_completed_modules
from app.services.restart import activity_round
from app.services.rewards import (
    SUPPORT_LEVEL,
    answer_given_away,
    on_attempt,
    on_bonus_quest,
    real_work,
)


def hint_level_seen(session: Session, user_id: int, activity_id: int, round: int = 0) -> int:
    """The highest hint level this student has been shown on this activity in this round of its
    module (app/services/restart.py; 0 unless they restarted it); 0 for none."""
    seen = session.scalar(
        select(func.max(HintView.level)).where(
            HintView.user_id == user_id,
            HintView.activity_id == activity_id,
            HintView.round == round,
        )
    )
    return seen or 0


class BlankAnswer(ValueError):
    """The submission answers nothing (`checking.is_blank`), so it isn't recorded (#143)."""


class AlreadyAnswered(ValueError):
    """A one-answer item (the mastery check, #144) that this student has answered already."""


def bonus_quests(session: Session) -> list[int]:
    """The course's bonus quests (FR-8.3, #87): visible bonus activities that a module segment
    shows, in id order. A hidden or unplaced one can't be reached, so it never counts towards All
    Quests."""
    placed = select(Segment.activity_id).where(
        Segment.module_id.is_not(None), Segment.activity_id.is_not(None)
    )
    return list(
        session.scalars(
            select(Activity.id)
            .where(
                Activity.purpose == "bonus",
                Activity.visible.is_(True),
                Activity.id.in_(placed),
            )
            .order_by(Activity.id)
        )
    )


def reward_bonus_quest(session: Session, user_id: int, activity: Activity) -> None:
    """A bonus quest answered correctly before the hints gave it away (FR-8.3, FR-9.3; #87): its
    20 points and its Quest badge, once, and All Quests once every quest in the course is earned.
    The badge's ref is the quest's activity id, so it keeps pointing at the same quest if another
    is retired; the badge shelf numbers them for display. Never touches mastery: a bonus item
    counts towards no objective."""
    quests = bonus_quests(session)
    if activity.id not in quests:  # hidden or unplaced: only staff can answer it, as a preview
        return
    earned = set(
        session.scalars(
            select(Attempt.activity_id).where(
                Attempt.user_id == user_id,
                Attempt.activity_id.in_(quests),
                Attempt.correct.is_(True),
                real_work(),
            )
        )
    )
    on_bonus_quest(
        session,
        user_id,
        activity.id,
        all_quests_done=set(quests) <= earned,
    )


def record_attempt(
    session: Session,
    user_id: int,
    activity: Activity,
    submitted: dict[str, Any],
    *,
    one_answer: bool = False,
) -> tuple[Attempt, CheckResult]:
    """Grade `submitted` by comparison with the stored solution and add the attempt, any points it
    earns and, for a mastery item, the student's objective results to the session (not
    committed). Raises pydantic's ValidationError if `submitted` is not in the kind's shape, and
    BlankAnswer, recording nothing, if it answers nothing.

    Holds the student's write lock (app/services/locks.py) from before the attempt is inserted
    until the caller commits, so two answers sent at once are graded and recorded one after the
    other: the second sees the first's points and results instead of racing it (#138). Raises
    `ActivityGone` if the activity was deleted meanwhile.

    With `one_answer` (a mastery check item, #144) it raises `AlreadyAnswered` if the student has
    an attempt at it already. That is checked under the student's lock, after the submission has
    passed every other check, so a refused submission never uses up the one answer and two sent
    at once can't both be recorded."""
    result = check_activity(activity.kind, activity.config, activity.solution, submitted)
    if is_blank(activity.kind, submitted):
        raise BlankAnswer(activity.id)
    hold_activity(session, activity.id)  # before the student: see app/services/locks.py
    lock_student(session, user_id)  # before any insert (#138)
    if one_answer and answered(session, user_id, activity.id):
        raise AlreadyAnswered(activity.id)
    attempt = Attempt(
        user_id=user_id,
        activity_id=activity.id,
        submitted=submitted,
        correct=result.correct,
        score=result.score,
        detail=result.model_dump(),
        hint_level=hint_level_seen(
            session, user_id, activity.id, activity_round(session, user_id, activity).number
        ),
    )
    session.add(attempt)
    session.flush()
    # Rewards go by every round: hint 3 or 4 before a restart still gave the answer away.
    real = attempt.hint_level < SUPPORT_LEVEL and not answer_given_away(
        session, user_id, activity.id, before=attempt.id
    )
    if activity.purpose == "bonus":
        # A bonus quest earns its own points and badge instead of an activity's (FR-8.3, #87),
        # and only for real work: hints 3 and 4 give the answer away, so after them it earns
        # nothing (ID doc: badges mark real progress).
        if result.correct and real:
            reward_bonus_quest(session, user_id, activity)
    elif not in_check(activity):  # a module 6 item's points wait for the end of the check (#144)
        on_attempt(session, attempt)  # points for a first correct answer (FR-9.1, FR-9.2)
    if result.correct and real and activity.purpose != "bonus":
        # Real work in a module already complete earns its reward now (#166 review). An optional
        # bonus quest isn't the module's work: it earns its own reward.
        reward_completed_modules(session, user_id, activity)
    if counts(activity):
        recompute(session, user_id)  # the objective results, and what they earn (FR-7)
    return attempt, result


def answered(session: Session, user_id: int, activity_id: int) -> bool:
    """Whether this student has any attempt at the activity."""
    return (
        session.scalar(
            select(Attempt.id)
            .where(Attempt.user_id == user_id, Attempt.activity_id == activity_id)
            .limit(1)
        )
        is not None
    )


def answered_correctly(
    session: Session, user_id: int, activity_id: int, after: int | None = None
) -> bool:
    """Whether this student has a correct attempt at the activity: only attempts with an id above
    `after` if given (since the module's restart, app/services/restart.py)."""
    query = select(Attempt.id).where(
        Attempt.user_id == user_id,
        Attempt.activity_id == activity_id,
        Attempt.correct.is_(True),
    )
    if after is not None:
        query = query.where(Attempt.id > after)
    return session.scalar(query.limit(1)) is not None


def reveal_next_hint(
    session: Session, user_id: int, activity: Activity, *, limit: int | None = None
) -> tuple[Hint, Hint | None] | None:
    """Record that this student was shown their next hint level (not committed). Returns that hint
    and the one after it (None if it was the last), or None if every level has been shown, or
    every level up to `limit` (the mastery check's, #144).

    Holds the student's write lock until the caller commits, so two requests sent at once reveal
    two levels in turn rather than the same level twice (#138), and can't pass the `limit`
    together either. Raises `ActivityGone` like `record_attempt`."""
    hold_activity(session, activity.id)  # before the student: see app/services/locks.py
    lock_student(session, user_id)
    hints = session.scalars(
        select(Hint).where(Hint.activity_id == activity.id).order_by(Hint.level)
    ).all()
    round = activity_round(session, user_id, activity).number  # a restarted module (restart.py)
    seen = hint_level_seen(session, user_id, activity.id, round)
    hint = next((h for h in hints if h.level > seen), None)
    if hint is None or (limit is not None and hint.level > limit):
        return None
    # The newest attempt now: under the student's lock, so their next attempt gets a higher id.
    newest = session.scalar(select(func.max(Attempt.id))) or 0
    session.add(
        HintView(
            user_id=user_id,
            activity_id=activity.id,
            level=hint.level,
            round=round,
            after_attempt=newest,
        )
    )
    log_event(
        session,
        user_id,
        "hint_shown",
        f"activity:{activity.id}",
        {"level": hint.level, **({"round": round} if round else {})},
    )
    session.flush()
    return hint, next((h for h in hints if h.level > hint.level), None)
