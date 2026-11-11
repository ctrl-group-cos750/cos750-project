"""The activity routes: show an activity, grade an answer, and the hint ladder (FR-4, FR-5).

Every route first checks that this student may open the activity where the course shows it
(app/services/access.py, #137): 403 while its module is locked or its review path closed, 404
for one that is no longer part of the course. Staff may open every activity, to preview it.
Answers and hint requests are rate-limited per student (NFR-S6, #139).
"""

import json

from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select

from app.auth import CurrentUser
from app.db import DbSession
from app.models import Activity, Hint, User
from app.rate_limit import RateLimiter
from app.schemas.activities import (
    MAX_SUBMISSION_BYTES,
    ActivityOut,
    AttemptIn,
    AttemptOut,
    HintOut,
)
from app.schemas.ids import RowId
from app.services.access import activity_refusal
from app.services.attempts import hint_level_seen, record_attempt, reveal_next_hint
from app.services.locking import ActivityGone

router = APIRouter(prefix="/api/activities", tags=["activities"])

NOT_FOUND = "This activity does not exist."
RETIRED = "This activity is no longer part of the course."
MODULE_LOCKED = (
    "This activity is in a module that isn't open yet. Finish the modules before it first."
)
BAD_SUBMISSION = "This submission is not in the expected shape."
TOO_LARGE = "This answer is too long to check."
NO_MORE_HINTS = "You have seen every hint for this activity."
REVIEW_CLOSED = "This activity is on a review path, which opens when the mastery check marks its objective 'not yet'."
SUPPORT_LEVEL = 3  # hint levels 3 and 4 make a correct answer count as "with support" (FR-7.2)

# Per student (not per address: a campus or residence shares one). A student answering as fast as
# they can still reads the feedback between answers, which takes a second or more; a multiple
# choice item has at most 10 options and the hint ladder 4 levels. So 60 answers and 30 hint
# reveals a minute are never reached by hand, and they bound what one account can write.
attempts_limiter = RateLimiter(
    limit=60, window=60, message="You're answering very fast. Wait a moment and try again."
)
hints_limiter = RateLimiter(
    limit=30, window=60, message="That's a lot of hints at once. Wait a moment and try again."
)


def _activity_or_404(session: DbSession, activity_id: int, user: User) -> Activity:
    """The activity, if this student may open it where the course shows it (#137): 404 if there is
    no such activity or it was retired, 403 while its module is locked (FR-2.1) or, on a review
    path, until the path is open (FR-7.5), so module 6's and the review paths' fresh items stay
    unseen until the student gets there (FR-7.1)."""
    activity = session.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    refusal = activity_refusal(session, user, activity)
    if refusal == "retired":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=RETIRED)
    if refusal == "review_closed":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=REVIEW_CLOSED)
    if refusal == "module_locked":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=MODULE_LOCKED)
    return activity


@router.get("/{activity_id}", response_model=ActivityOut)
def get_activity(activity_id: RowId, session: DbSession, user: CurrentUser) -> Activity:
    """The activity to render. `ActivityOut` has no `solution`, so the answer never reaches the
    browser (FR-5.3, NFR-S2). 403 while the activity's module is locked or its review path is
    closed, 404 if it doesn't exist or is no longer part of the course."""
    return _activity_or_404(session, activity_id, user)


@router.post("/{activity_id}/attempts", status_code=status.HTTP_201_CREATED)
def submit_attempt(
    activity_id: RowId, body: AttemptIn, user: CurrentUser, session: DbSession
) -> AttemptOut:
    """Grade a submission by comparison with the stored solution and record the attempt (FR-4.2,
    FR-4.5, FR-5.3).

    Send `{"submitted": {...}}` in the kind's shape: `{"selected": "<option id>"}` for multiple
    choice, `{"order": [...]}` for Parsons, `{"answers": {...}}` for fill-in, and
    `{"rows": [{"visitedVertex", "queue", "visited", "order"}, ...]}` for a trace table, one row
    per BFS step (graded against the engine, so a trace has no stored solution). A submission in the
    wrong shape is 422. No student code is executed: `check_activity` compares the submission with
    the solution, which stays in this process (NFR-S7).

    Each kind's shape bounds its lengths, and the whole submission is at most
    `MAX_SUBMISSION_BYTES` (413 past it). 403 and 404 as for GET. 429 with `Retry-After` past 60
    answers a minute from one student. Two answers sent at once are recorded one after the other
    (app/services/locking.py)."""
    attempts_limiter.check(f"user:{user.id}")
    activity = _activity_or_404(session, activity_id, user)
    if len(json.dumps(body.submitted, separators=(",", ":"))) > MAX_SUBMISSION_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=TOO_LARGE)
    try:
        attempt, result = record_attempt(session, user.id, activity, body.submitted)
    except ValidationError as exc:  # the submission didn't match the kind's shape
        raise HTTPException(422, detail=BAD_SUBMISSION) from exc  # constant is deprecated upstream
    except ActivityGone:  # the seed deleted it while this answer waited
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND) from None
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


@router.get("/{activity_id}/hints")
def get_revealed_hints(activity_id: RowId, user: CurrentUser, session: DbSession) -> list[HintOut]:
    """Every hint level this student has already unlocked on this activity (FR-4.4, FR-4.5).

    Returns an empty list if they have not asked for any hints yet. 403 and 404 as for GET."""
    activity = _activity_or_404(session, activity_id, user)
    all_hints = session.scalars(
        select(Hint).where(Hint.activity_id == activity.id).order_by(Hint.level)
    ).all()
    seen = hint_level_seen(session, user.id, activity.id)
    out: list[HintOut] = []
    for h in all_hints:
        if h.level <= seen:
            following = next((f for f in all_hints if f.level > h.level), None)
            out.append(
                HintOut(
                    level=h.level,
                    body=h.body,
                    has_more=following is not None,
                    next_counts_as_support=following is not None
                    and following.level >= SUPPORT_LEVEL,
                )
            )
    return out


@router.post("/{activity_id}/hints", status_code=status.HTTP_201_CREATED)
def reveal_hint(activity_id: RowId, user: CurrentUser, session: DbSession) -> HintOut:
    """Reveal this student's next hint level, one at a time, and record it (FR-4.4, FR-4.5).

    No body. Each call returns the next level (1, then 2, …); once every level has been shown it
    is 409. When `nextCountsAsSupport` is true, warn the student before calling again: a correct
    answer after hint 3 or 4 counts as "met with support" (ID document §7.4).

    403 and 404 as for GET. 429 with `Retry-After` past 30 reveals a minute from one student. Two
    requests sent at once reveal two levels in turn, never the same level twice."""
    hints_limiter.check(f"user:{user.id}")
    activity = _activity_or_404(session, activity_id, user)
    try:
        revealed = reveal_next_hint(session, user.id, activity)
    except ActivityGone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND) from None
    if revealed is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=NO_MORE_HINTS)
    session.commit()
    hint, following = revealed
    return HintOut(
        level=hint.level,
        body=hint.body,
        has_more=following is not None,
        next_counts_as_support=following is not None and following.level >= SUPPORT_LEVEL,
    )
