from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError
from sqlalchemy import func, select

from app.auth import CurrentUser
from app.db import DbSession
from app.models import Activity, Attempt, Hint, HintView
from app.schemas.activities import ActivityOut, AttemptIn, AttemptOut, HintOut
from app.services.checking import check_activity

router = APIRouter(prefix="/api/activities", tags=["activities"])

NOT_FOUND = "This activity does not exist."
BAD_SUBMISSION = "This submission is not in the expected shape."
NO_MORE_HINTS = "You have seen every hint for this activity."
SUPPORT_LEVEL = 3  # hint levels 3 and 4 make a correct answer count as "with support" (FR-7.2)


def _activity_or_404(session: DbSession, activity_id: int) -> Activity:
    activity = session.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return activity


def _hint_level_seen(session: DbSession, user_id: int, activity_id: int) -> int:
    """The highest hint level this student has been shown on this activity; 0 for none."""
    seen = session.scalar(
        select(func.max(HintView.level)).where(
            HintView.user_id == user_id, HintView.activity_id == activity_id
        )
    )
    return seen or 0


@router.get("/{activity_id}", response_model=ActivityOut)
def get_activity(activity_id: int, session: DbSession, _user: CurrentUser) -> Activity:
    """The activity to render. `ActivityOut` has no `solution`, so the answer never reaches the
    browser (FR-5.3, NFR-S2)."""
    return _activity_or_404(session, activity_id)


@router.post("/{activity_id}/attempts", status_code=status.HTTP_201_CREATED)
def submit_attempt(
    activity_id: int, body: AttemptIn, user: CurrentUser, session: DbSession
) -> AttemptOut:
    """Grade a submission by comparison with the stored solution and record the attempt (FR-4.2,
    FR-4.5, FR-5.3).

    Send `{"submitted": {...}}` in the kind's shape: `{"selected": "<option id>"}` for multiple
    choice, `{"order": [...]}` for Parsons, `{"answers": {...}}` for fill-in. A submission in the
    wrong shape is 422. No student code is executed: `check_activity` compares the submission with
    the solution, which stays in this process (NFR-S7)."""
    activity = _activity_or_404(session, activity_id)
    try:
        result = check_activity(activity.kind, activity.config, activity.solution, body.submitted)
    except ValidationError as exc:  # the submission didn't match the kind's shape
        raise HTTPException(422, detail=BAD_SUBMISSION) from exc  # constant is deprecated upstream
    attempt = Attempt(
        user_id=user.id,
        activity_id=activity.id,
        submitted=body.submitted,
        correct=result.correct,
        score=result.score,
        detail=result.model_dump(),
        hint_level=_hint_level_seen(session, user.id, activity.id),
    )
    session.add(attempt)
    session.commit()
    return AttemptOut(
        id=attempt.id,
        activity_id=activity.id,
        correct=result.correct,
        score=result.score,
        parts=result.parts,
        feedback=result.feedback,
        hint_level=attempt.hint_level,
    )


@router.post("/{activity_id}/hints", status_code=status.HTTP_201_CREATED)
def reveal_hint(activity_id: int, user: CurrentUser, session: DbSession) -> HintOut:
    """Reveal this student's next hint level, one at a time, and record it (FR-4.4, FR-4.5).

    No body. Each call returns the next level (1, then 2, …); once every level has been shown it
    is 409. When `nextCountsAsSupport` is true, warn the student before calling again: a correct
    answer after hint 3 or 4 counts as "met with support" (ID document §7.4)."""
    activity = _activity_or_404(session, activity_id)
    hints = session.scalars(
        select(Hint).where(Hint.activity_id == activity.id).order_by(Hint.level)
    ).all()
    seen = _hint_level_seen(session, user.id, activity.id)
    hint = next((h for h in hints if h.level > seen), None)
    if hint is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=NO_MORE_HINTS)
    session.add(HintView(user_id=user.id, activity_id=activity.id, level=hint.level))
    session.commit()
    following = next((h for h in hints if h.level > hint.level), None)
    return HintOut(
        level=hint.level,
        body=hint.body,
        has_more=following is not None,
        next_counts_as_support=following is not None and following.level >= SUPPORT_LEVEL,
    )
