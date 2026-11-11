from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select

from app.auth import CurrentUser
from app.db import DbSession
from app.models import Activity, Hint, User
from app.schemas.activities import ActivityOut, AttemptIn, AttemptOut, HintOut
from app.services.attempts import (
    BlankAnswer,
    answered,
    answered_correctly,
    hint_level_seen,
    record_attempt,
    reveal_next_hint,
)
from app.services.mastery import in_check, review_open, review_path_of
from app.services.modules import activity_locked

router = APIRouter(prefix="/api/activities", tags=["activities"])

NOT_FOUND = "This activity does not exist."
BAD_SUBMISSION = "This submission is not in the expected shape."
BLANK = "Answer the activity before checking it."
NO_MORE_HINTS = "You have seen every hint for this activity."
SOLVED = "You have already answered this correctly, so no more hints are given."
REVIEW_CLOSED = "This activity is on a review path, which opens when the mastery check marks its objective 'not yet'."
MODULE_LOCKED = (
    "This activity is in a module that isn't open yet. Complete the module before it to unlock it."
)
ALREADY_ANSWERED = (
    "You have answered this mastery check question. Only your first answer counts, so it can't "
    "be changed. Your results are in your mastery report once you finish the check."
)
ANSWERED_NO_HINTS = "You have answered this mastery check question, so no more hints are given."
HINT_LIMIT = (
    "The mastery check gives two hints at most. If you need more, answer as best you can: "
    "if this objective comes out 'not yet', its review path teaches it again with every hint."
)
RECORDED = (
    "Answer recorded. You will see your results in your mastery report when you finish the check."
)
SUPPORT_LEVEL = 3  # hint levels 3 and 4 make a correct answer count as "with support" (FR-7.2)
# The highest hint a mastery check item gives (#144): hints 3 and 4 give the answer away, so a
# student who needs them goes to the review path instead (FR-7.5).
MASTERY_HINT_LIMIT = 2


def _checked(activity: Activity, user: User) -> bool:
    """Whether the mastery check's rules apply: a module 6 item, answered by a student (#144).
    Staff are let through, so the content editor's "Open as a student" still shows each result."""
    return in_check(activity) and not user.is_staff


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


def _activity_or_404(session: DbSession, activity_id: int, user: User) -> Activity:
    """The activity, if this student may open it. An activity in a module is 403 while that module
    is locked (FR-2.1), so module 6's mastery items stay unseen until module 6 opens (FR-7.1); that
    covers a video checkpoint's question too, through the module that plays the video. An activity
    on a review path is 403 until the path is open (FR-7.5): its fresh items must still be unseen
    when the student gets there. Staff are let through both, so the content editor's "Open as a
    student" works on any item (the team checks content that way)."""
    activity = session.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    if user.is_staff:
        return activity
    if activity_locked(session, user.id, activity):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=MODULE_LOCKED)
    objective = review_path_of(session, activity_id)
    if objective is not None and not review_open(session, user.id, objective):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=REVIEW_CLOSED)
    return activity


@router.get("/{activity_id}")
def get_activity(activity_id: int, session: DbSession, user: CurrentUser) -> ActivityOut:
    """The activity to render. `ActivityOut` has no `solution`, so the answer never reaches the
    browser (FR-5.3, NFR-S2). `solved` says whether this student has already answered it
    correctly, so the page stops offering hints after a refresh too (#158)."""
    activity = _activity_or_404(session, activity_id, user)
    out = ActivityOut.model_validate(activity)
    if _checked(activity, user):  # says it was answered, never whether it was right (#144)
        out.mastery_check = True
        out.answered = answered(session, user.id, activity.id)
    else:
        out.solved = answered_correctly(session, user.id, activity.id)
    return out


@router.post("/{activity_id}/attempts", status_code=status.HTTP_201_CREATED)
def submit_attempt(
    activity_id: int, body: AttemptIn, user: CurrentUser, session: DbSession
) -> AttemptOut:
    """Grade a submission by comparison with the stored solution and record the attempt (FR-4.2,
    FR-4.5, FR-5.3).

    Send `{"submitted": {...}}` in the kind's shape: `{"selected": "<option id>"}` for multiple
    choice, `{"order": [...]}` for Parsons, `{"answers": {...}}` for fill-in, and
    `{"rows": [{"visitedVertex", "queue", "visited", "order"}, ...]}` for a trace table, one row
    per BFS step (graded against the engine, so a trace has no stored solution). A submission in the
    wrong shape, or one that answers nothing (no option, line, token, pair, test or row), is 422
    and isn't recorded. No student code is executed: `check_activity` compares the submission with
    the solution, which stays in this process (NFR-S7).

    A module 6 mastery item takes one answer only (409 after it), and its response is `withheld`:
    no `correct`, `score` or `parts`, so the network tab gives nothing away either (#144). The
    mastery report shows the results once every item is answered."""
    activity = _activity_or_404(session, activity_id, user)
    checked = _checked(activity, user)
    if checked and answered(session, user.id, activity.id):
        raise HTTPException(status.HTTP_409_CONFLICT, detail=ALREADY_ANSWERED)
    try:
        attempt, result = record_attempt(session, user.id, activity, body.submitted)
    except ValidationError as exc:  # the submission didn't match the kind's shape
        raise HTTPException(422, detail=BAD_SUBMISSION) from exc  # constant is deprecated upstream
    except BlankAnswer as exc:  # nothing chosen: not an attempt (#143)
        raise HTTPException(422, detail=BLANK) from exc
    session.commit()
    if checked:
        return AttemptOut(
            id=attempt.id,
            activity_id=activity.id,
            correct=None,
            score=None,
            parts=[],
            feedback=RECORDED,
            hint_level=attempt.hint_level,
            withheld=True,
        )
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
def get_revealed_hints(activity_id: int, user: CurrentUser, session: DbSession) -> list[HintOut]:
    """Every hint level this student has already unlocked on this activity (FR-4.4, FR-4.5).

    Returns an empty list if they have not asked for any hints yet."""
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
def reveal_hint(activity_id: int, user: CurrentUser, session: DbSession) -> HintOut:
    """Reveal this student's next hint level, one at a time, and record it (FR-4.4, FR-4.5).

    No body. Each call returns the next level (1, then 2, …); once every level has been shown,
    or once the student has answered correctly, it is 409. When `nextCountsAsSupport` is true,
    warn the student before calling again: a correct answer after hint 3 or 4 counts as "met
    with support" (ID document §7.4).

    A module 6 mastery item gives hints 1 and 2 only (#144): asking for a third is 409, and the
    second says `limitReached`. Once the item is answered it is 409 too, with a message that
    doesn't say whether the answer was right."""
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
    revealed = reveal_next_hint(session, user.id, activity, limit=limit)
    if revealed is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=NO_MORE_HINTS if limit is None else HINT_LIMIT
        )
    session.commit()
    hint, following = revealed
    return _hint_out(hint, following, limit)
