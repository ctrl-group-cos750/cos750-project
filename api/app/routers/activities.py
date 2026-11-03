from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError

from app.auth import CurrentUser
from app.db import DbSession
from app.models import Activity, Attempt
from app.schemas.activities import ActivityOut, AttemptIn, AttemptOut
from app.services.checking import check_code_activity

router = APIRouter(prefix="/api/activities", tags=["activities"])

NOT_FOUND = "This activity does not exist."
BAD_SUBMISSION = "This submission is not in the expected shape."


def _activity_or_404(session: DbSession, activity_id: int) -> Activity:
    activity = session.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return activity


@router.get("/{activity_id}", response_model=ActivityOut)
def get_activity(activity_id: int, session: DbSession, _user: CurrentUser) -> Activity:
    """The activity to render. `ActivityOut` has no `solution`, so the answer never reaches the
    browser (FR-5.3, NFR-S2)."""
    return _activity_or_404(session, activity_id)


@router.post(
    "/{activity_id}/attempts", status_code=status.HTTP_201_CREATED
)
def submit_attempt(
    activity_id: int, body: AttemptIn, user: CurrentUser, session: DbSession
) -> AttemptOut:
    """Grade a submission by comparison with the stored solution and record the attempt (FR-5.3).

    No student code is executed: `check_code_activity` compares the submission with the solution,
    which stays in this process (NFR-S7)."""
    activity = _activity_or_404(session, activity_id)
    try:
        result = check_code_activity(
            activity.kind, activity.config, activity.solution, body.submitted
        )
    except ValidationError as exc:  # the submission didn't match the kind's shape
        raise HTTPException(422, detail=BAD_SUBMISSION) from exc  # constant is deprecated upstream
    attempt = Attempt(
        user_id=user.id,
        activity_id=activity.id,
        submitted=body.submitted,
        correct=result.correct,
        score=result.score,
        detail=result.model_dump(),
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
    )
