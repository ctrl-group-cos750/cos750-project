"""The activity routes: show an activity, grade an answer, and the hint ladder (FR-4, FR-5).

Every route first checks that this student may open the activity where the course shows it
(app/services/access.py, #137): 403 while its module is locked or its review path closed, 404
for one that is no longer part of the course. Staff may open every activity, to preview it.
Answers and hint requests are rate-limited per student (NFR-S6, #139).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy import select

from app.auth import CurrentUser
from app.db import DbSession
from app.models import Activity, Attempt, Hint, User
from app.rate_limit import RateLimiter
from app.schemas.activities import (
    MAX_SUBMISSION_BYTES,
    ActivityOut,
    AttemptIn,
    AttemptOut,
    HintOut,
    LastAttemptOut,
    PartResult,
)
from app.schemas.ids import RowId
from app.services.access import activity_refusal
from app.services.attempts import (
    AlreadyAnswered,
    BlankAnswer,
    answered,
    answered_correctly,
    hint_level_seen,
    record_attempt,
    reveal_next_hint,
)
from app.services.locks import ActivityGone
from app.services.mastery import in_check
from app.services.submissions import clean, submission_problem

router = APIRouter(prefix="/api/activities", tags=["activities"])

NOT_FOUND = "This activity does not exist."
RETIRED = "This activity is no longer part of the course."
BAD_SUBMISSION = "This submission is not in the expected shape."
TOO_LARGE = "This answer is too long to check."
BLANK = "Answer the activity before checking it."
FOREIGN = "This answer names something that isn't in this activity."
NO_MORE_HINTS = "You have seen every hint for this activity."
SOLVED = "You have already answered this correctly, so no more hints are given."
REVIEW_CLOSED = "This activity is on a review path, which opens when the mastery check marks its objective 'not yet'."
MODULE_LOCKED = (
    "This activity is in the mastery check, which opens once modules 1 to 5 are each complete or "
    "tested out."
)
QUICK_CHECK = (
    "This question is part of a module's quick check. Take the quick check from the module's page."
)
ALREADY_ANSWERED = (
    "You have answered this mastery check question. Only your first answer counts, so it can't "
    "be changed. Your results are in your mastery report once every question in the check is "
    "answered."
)
ANSWERED_NO_HINTS = "You have answered this mastery check question, so no more hints are given."
HINT_LIMIT = (
    "The mastery check gives two hints at most. If you need more, answer as best you can: "
    "if this objective comes out 'not yet', its review path teaches it again with every hint."
)
RECORDED = (
    "Answer recorded. Your results are in your mastery report once every question in the check "
    "is answered."
)
NOT_SHOWN = "This activity is extra help that isn't part of your way through the module."
SUPPORT_LEVEL = 3  # hint levels 3 and 4 make a correct answer count as "with support" (FR-7.2)
# The highest hint a mastery check item gives (#144): hints 3 and 4 give the answer away, so a
# student who needs them goes to the review path instead (FR-7.5).
MASTERY_HINT_LIMIT = 2


def _checked(activity: Activity, user: User) -> bool:
    """Whether the mastery check's rules apply: a module 6 item, answered by a student (#144).
    Staff are let through, so the content editor's "Open as a student" still shows each result."""
    return in_check(activity) and not user.is_staff


def _attempt_out(attempt: Attempt, checked: bool) -> AttemptOut:
    """An attempt's result as the student is shown it: in full, or `withheld` on a mastery check
    item (#144), where nothing says whether it was right."""
    if checked:
        return AttemptOut(
            id=attempt.id,
            activity_id=attempt.activity_id,
            correct=None,
            score=None,
            parts=[],
            feedback=RECORDED,
            hint_level=attempt.hint_level,
            withheld=True,
        )
    return AttemptOut(
        id=attempt.id,
        activity_id=attempt.activity_id,
        correct=attempt.correct,
        score=attempt.score,
        parts=[PartResult.model_validate(p) for p in (attempt.detail or {}).get("parts", [])],
        feedback=str((attempt.detail or {}).get("feedback", "")),
        hint_level=attempt.hint_level,
    )


def _last_attempt(session: DbSession, user: User, activity: Activity) -> LastAttemptOut | None:
    """This student's latest answer to the activity and its result (#171), or None."""
    attempt = session.scalar(
        select(Attempt)
        .where(Attempt.user_id == user.id, Attempt.activity_id == activity.id)
        .order_by(Attempt.id.desc())
        .limit(1)
    )
    if attempt is None:
        return None
    return LastAttemptOut(
        submitted=attempt.submitted, result=_attempt_out(attempt, _checked(activity, user))
    )


def _hint_out(hint: Hint, following: Hint | None, limit: int | None) -> HintOut:
    """A hint as the student sees it. With a `limit`, a hint past it counts as not there."""
    held_back = following is not None and limit is not None and following.level > limit
    offered = None if held_back else following
    return HintOut(
        level=hint.level,
        body=hint.body,
        has_more=offered is not None,
        next_counts_as_support=offered is not None and offered.level >= SUPPORT_LEVEL,
        limit_reached=held_back,
    )


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


async def _body_bytes(request: Request) -> int:
    """The size of the request body as it arrived, in bytes (UTF-8 JSON as the browser sends it).
    FastAPI has already read the body to parse it, so this costs nothing more."""
    return len(await request.body())


BodyBytes = Annotated[int, Depends(_body_bytes)]


def _activity_or_404(session: DbSession, activity_id: int, user: User) -> Activity:
    """The activity, if this student may open it where the course shows it (#137): 404 if there is
    no such activity or it was retired, 403 while its module is locked (FR-2.1) or, on a review
    path, until the path is open (FR-7.5), and a support item while it isn't shown to this student
    (FR-8.4), so module 6's and the review paths' fresh items stay
    unseen until the student gets there (FR-7.1). Staff are let through, so the content editor's
    "Open as a student" works on any item (the team checks content that way)."""
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
    if refusal == "quick_check":  # answered only in the quick check (FR-8.2, #214)
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=QUICK_CHECK)
    if refusal == "not_shown":  # a support item this student isn't shown (FR-8.4)
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=NOT_SHOWN)
    return activity


@router.get("/{activity_id}")
def get_activity(activity_id: RowId, session: DbSession, user: CurrentUser) -> ActivityOut:
    """The activity to render. `ActivityOut` has no `solution`, so the answer never reaches the
    browser (FR-5.3, NFR-S2). `solved` says whether this student has already answered it
    correctly, so the page stops offering hints after a refresh too (#158), and `lastAttempt`
    holds this student's latest answer and the result for it, as marked now, so coming back to an
    activity shows it (#171; withheld on a mastery check item, as when answered). 403 while the
    activity's module is locked or its review path is closed, 404 if it doesn't exist or is no
    longer part of the course."""
    activity = _activity_or_404(session, activity_id, user)
    out = ActivityOut.model_validate(activity)
    if _checked(activity, user):  # says it was answered, never whether it was right (#144)
        out.mastery_check = True
        out.answered = answered(session, user.id, activity.id)
    else:
        out.solved = answered_correctly(session, user.id, activity.id)
    out.last_attempt = _last_attempt(session, user, activity)  # coming back shows it (#171)
    return out


@router.post("/{activity_id}/attempts", status_code=status.HTTP_201_CREATED)
def submit_attempt(
    activity_id: RowId,
    body: AttemptIn,
    user: CurrentUser,
    session: DbSession,
    body_bytes: BodyBytes,
) -> AttemptOut:
    """Grade a submission by comparison with the stored solution and record the attempt (FR-4.2,
    FR-4.5, FR-5.3).

    Send `{"submitted": {...}}` in the kind's shape: `{"selected": "<option id>"}` for multiple
    choice, `{"order": [...]}` for Parsons, `{"answers": {...}}` for fill-in, and
    `{"rows": [{"visitedVertex", "queue", "visited", "order"}, ...]}` for a trace table, one row
    per BFS step (graded against the engine, so a trace has no stored solution). A submission in the
    wrong shape is 422. No student code is executed: `check_activity` compares the submission with
    the solution, which stays in this process (NFR-S7).

    Each kind's shape bounds its lengths, and the request body is at most `MAX_SUBMISSION_BYTES`
    bytes (413 past it). A matching pair or fill-in blank sent as "" (a reset select) counts as
    unanswered. A submission that answers nothing (no option, line, token, pair, test or row), or
    one naming an option, line, blank, token, test case or vertex the activity doesn't have, is
    422 and not recorded. 403 and 404 as for GET. 429 with `Retry-After` past 60 answers a minute
    from one student. Two answers sent at once are recorded one after the other
    (app/services/locks.py).

    A module 6 mastery item takes one answer only (409 after it), and its response is `withheld`:
    no `correct`, `score` or `parts`, so the network tab gives nothing away either (#144). The
    mastery report shows the results once every item is answered. The 409 comes after every
    other check, so a refused (413, 422, 429) submission never uses up that one answer."""
    attempts_limiter.check(f"user:{user.id}")
    activity = _activity_or_404(session, activity_id, user)
    if body_bytes > MAX_SUBMISSION_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=TOO_LARGE)
    checked = _checked(activity, user)
    try:
        # Not an answer at all: refused before it can spend a first (counted) attempt (#139).
        # A reset select ("") is a choice not made; what is stored is what was chosen.
        submitted = clean(activity.kind, body.submitted)
        if submission_problem(activity.kind, activity.config, submitted) is not None:
            raise HTTPException(422, detail=FOREIGN)
        attempt, _ = record_attempt(session, user.id, activity, submitted, one_answer=checked)
    except AlreadyAnswered:  # the mastery check takes one answer (#144)
        raise HTTPException(status.HTTP_409_CONFLICT, detail=ALREADY_ANSWERED) from None
    except ValidationError as exc:  # the submission didn't match the kind's shape
        raise HTTPException(422, detail=BAD_SUBMISSION) from exc  # constant is deprecated upstream
    except BlankAnswer as exc:  # nothing chosen: not an attempt (#143)
        raise HTTPException(422, detail=BLANK) from exc
    except ActivityGone:  # the seed deleted it while this answer waited
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND) from None
    session.commit()
    return _attempt_out(attempt, checked)


@router.get("/{activity_id}/hints")
def get_revealed_hints(activity_id: RowId, user: CurrentUser, session: DbSession) -> list[HintOut]:
    """Every hint level this student has already unlocked on this activity (FR-4.4, FR-4.5).

    Returns an empty list if they have not asked for any hints yet. 403 and 404 as for GET."""
    activity = _activity_or_404(session, activity_id, user)
    all_hints = session.scalars(
        select(Hint).where(Hint.activity_id == activity.id).order_by(Hint.level)
    ).all()
    seen = hint_level_seen(session, user.id, activity.id)
    limit = MASTERY_HINT_LIMIT if _checked(activity, user) else None
    out: list[HintOut] = []
    for h in all_hints:
        if h.level <= seen:
            following = next((f for f in all_hints if f.level > h.level), None)
            out.append(_hint_out(h, following, limit))
    return out


@router.post("/{activity_id}/hints", status_code=status.HTTP_201_CREATED)
def reveal_hint(activity_id: RowId, user: CurrentUser, session: DbSession) -> HintOut:
    """Reveal this student's next hint level, one at a time, and record it (FR-4.4, FR-4.5).

    No body. Each call returns the next level (1, then 2, …); once every level has been shown,
    or once the student has answered correctly, it is 409. When `nextCountsAsSupport` is true,
    warn the student before calling again: a correct answer after hint 3 or 4 counts as "met
    with support" (ID document §7.4).

    A module 6 mastery item gives hints 1 and 2 only (#144): asking for a third is 409, and the
    second says `limitReached`. Once the item is answered it is 409 too, with a message that
    doesn't say whether the answer was right.

    403 and 404 as for GET. 429 with `Retry-After` past 30 reveals a minute from one student. Two
    requests sent at once reveal two levels in turn, never the same level twice."""
    hints_limiter.check(f"user:{user.id}")
    activity = _activity_or_404(session, activity_id, user)
    limit = None
    if _checked(activity, user):
        if answered(session, user.id, activity.id):
            raise HTTPException(status.HTTP_409_CONFLICT, detail=ANSWERED_NO_HINTS)
        limit = MASTERY_HINT_LIMIT
    # A hint after a right answer helps with nothing, and would count in the pilot's hint use as
    # help the student needed (#158).
    elif answered_correctly(session, user.id, activity.id):
        raise HTTPException(status.HTTP_409_CONFLICT, detail=SOLVED)
    try:
        revealed = reveal_next_hint(session, user.id, activity, limit=limit)
    except ActivityGone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND) from None
    if revealed is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=NO_MORE_HINTS if limit is None else HINT_LIMIT
        )
    session.commit()
    hint, following = revealed
    return _hint_out(hint, following, limit)
