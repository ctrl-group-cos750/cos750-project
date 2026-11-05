"""Recording a student's attempts and hint views (FR-4.2, FR-4.4, FR-4.5, FR-5.3).

The activity routes call these, and so does the demo-account seed (app/seed/demo_accounts.py), so
a demo account's history is graded and recorded exactly as a real student's would be.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Hint, HintView
from app.schemas.activities import CheckResult
from app.services.checking import check_activity


def hint_level_seen(session: Session, user_id: int, activity_id: int) -> int:
    """The highest hint level this student has been shown on this activity; 0 for none."""
    seen = session.scalar(
        select(func.max(HintView.level)).where(
            HintView.user_id == user_id, HintView.activity_id == activity_id
        )
    )
    return seen or 0


def record_attempt(
    session: Session, user_id: int, activity: Activity, submitted: dict[str, Any]
) -> tuple[Attempt, CheckResult]:
    """Grade `submitted` by comparison with the stored solution and add the attempt to the session
    (not committed). Raises pydantic's ValidationError if `submitted` is not in the kind's shape."""
    result = check_activity(activity.kind, activity.config, activity.solution, submitted)
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
    return attempt, result


def reveal_next_hint(
    session: Session, user_id: int, activity: Activity
) -> tuple[Hint, Hint | None] | None:
    """Record that this student was shown their next hint level (not committed). Returns that hint
    and the one after it (None if it was the last), or None if every level has been shown."""
    hints = session.scalars(
        select(Hint).where(Hint.activity_id == activity.id).order_by(Hint.level)
    ).all()
    seen = hint_level_seen(session, user_id, activity.id)
    hint = next((h for h in hints if h.level > seen), None)
    if hint is None:
        return None
    session.add(HintView(user_id=user_id, activity_id=activity.id, level=hint.level))
    session.flush()
    return hint, next((h for h in hints if h.level > hint.level), None)
