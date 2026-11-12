"""Recording a student's attempts and hint views (FR-4.2, FR-4.4, FR-4.5, FR-5.3).

The activity routes call these, and so does the demo-account seed (app/seed/demo_accounts.py), so
a demo account's history is graded and recorded exactly as a real student's would be.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Hint, HintView
from app.schemas.activities import CheckResult
from app.services.checking import check_activity, is_blank
from app.services.events import log_event
from app.services.locks import hold_activity, lock_student
from app.services.mastery import counts, recompute
from app.services.modules import reward_completed_modules
from app.services.rewards import SUPPORT_LEVEL, on_attempt


def hint_level_seen(session: Session, user_id: int, activity_id: int) -> int:
    """The highest hint level this student has been shown on this activity; 0 for none."""
    seen = session.scalar(
        select(func.max(HintView.level)).where(
            HintView.user_id == user_id, HintView.activity_id == activity_id
        )
    )
    return seen or 0


class BlankAnswer(ValueError):
    """The submission answers nothing (`checking.is_blank`), so it isn't recorded (#143)."""


def record_attempt(
    session: Session, user_id: int, activity: Activity, submitted: dict[str, Any]
) -> tuple[Attempt, CheckResult]:
    """Grade `submitted` by comparison with the stored solution and add the attempt, any points it
    earns and, for a mastery item, the student's objective results to the session (not
    committed). Raises pydantic's ValidationError if `submitted` is not in the kind's shape, and
    BlankAnswer, recording nothing, if it answers nothing.

    Holds the student's write lock (app/services/locks.py) from before the attempt is inserted
    until the caller commits, so two answers sent at once are graded and recorded one after the
    other: the second sees the first's points and results instead of racing it (#138). Raises
    `ActivityGone` if the activity was deleted meanwhile."""
    result = check_activity(activity.kind, activity.config, activity.solution, submitted)
    if is_blank(activity.kind, submitted):
        raise BlankAnswer(activity.id)
    hold_activity(session, activity.id)  # before the student: see app/services/locks.py
    lock_student(session, user_id)  # before any insert (#138)
    attempt = Attempt(
        user_id=user_id,
        activity_id=activity.id,
        submitted=submitted,
        correct=result.correct,
        score=result.score,
        detail=result.model_dump(),
        hint_level=hint_level_seen(session, user_id, activity.id),
    )
    session.add(attempt)
    session.flush()
    on_attempt(session, attempt)  # points for a first correct answer (FR-9.1, FR-9.2)
    if result.correct and attempt.hint_level < SUPPORT_LEVEL:
        # Real work in a module already complete earns its reward now (#166 review).
        reward_completed_modules(session, user_id, activity)
    if counts(activity):
        recompute(session, user_id)  # the objective results, and what they earn (FR-7)
    return attempt, result


def answered_correctly(session: Session, user_id: int, activity_id: int) -> bool:
    """Whether this student has a correct attempt at the activity."""
    return (
        session.scalar(
            select(Attempt.id)
            .where(
                Attempt.user_id == user_id,
                Attempt.activity_id == activity_id,
                Attempt.correct.is_(True),
            )
            .limit(1)
        )
        is not None
    )


def reveal_next_hint(
    session: Session, user_id: int, activity: Activity
) -> tuple[Hint, Hint | None] | None:
    """Record that this student was shown their next hint level (not committed). Returns that hint
    and the one after it (None if it was the last), or None if every level has been shown.

    Holds the student's write lock until the caller commits, so two requests sent at once reveal
    two levels in turn rather than the same level twice (#138). Raises `ActivityGone` like
    `record_attempt`."""
    hold_activity(session, activity.id)  # before the student: see app/services/locks.py
    lock_student(session, user_id)
    hints = session.scalars(
        select(Hint).where(Hint.activity_id == activity.id).order_by(Hint.level)
    ).all()
    seen = hint_level_seen(session, user_id, activity.id)
    hint = next((h for h in hints if h.level > seen), None)
    if hint is None:
        return None
    session.add(HintView(user_id=user_id, activity_id=activity.id, level=hint.level))
    log_event(session, user_id, "hint_shown", f"activity:{activity.id}", {"level": hint.level})
    session.flush()
    return hint, next((h for h in hints if h.level > hint.level), None)
