"""Router for module-map and progress endpoints (SE document §9, FR-2).

All endpoints but ``/length`` require an authenticated student (``CurrentUser``).  Every query is
scoped to ``user.id`` — never touches another student's data (NFR-S2, FR-1.3).

Endpoints
---------
GET  /api/modules                       → list[ModuleOut]
GET  /api/modules/length                → CourseLengthOut  (public: the register page shows it)
GET  /api/modules/{module_id}           → ModuleDetailOut
POST /api/modules/{module_id}/position  → ModuleDetailOut  (body: PositionIn)
GET  /api/modules/{module_id}/quick-check → QuickCheckOut
POST /api/modules/{module_id}/quick-check → QuickCheckResultOut  (body: QuickCheckIn)

Error mapping
-------------
``ModuleNotFound`` (service) → 404  "Module not found."
``ModuleLocked``   (service) → 403  "The mastery check opens once ..." (only module 6 locks)
``PositionTooFar`` (service) → 409  "Work through the module one segment at a time."
"""

from fastapi import APIRouter, HTTPException, status

from app.auth import CurrentUser
from app.db import DbSession
from app.schemas.ids import RowId
from app.schemas.modules import (
    CourseLengthOut,
    ModuleDetailOut,
    ModuleOut,
    PositionIn,
    QuickCheckIn,
    QuickCheckOut,
    QuickCheckResultOut,
)
from app.services.modules import (
    ModuleLocked,
    ModuleNotFound,
    PositionTooFar,
    RetrievalIncomplete,
    SegmentNotDone,
    course_minutes,
    get_module_detail,
    get_modules_for_user,
    save_position,
)
from app.services.quick_check import (
    Answer,
    AnswersDontFit,
    ModuleAlreadyDone,
    QuickCheckMissing,
    QuickCheckTaken,
    quick_check,
    take,
)

router = APIRouter(prefix="/api/modules", tags=["modules"])

# Student-friendly error messages (NFR-U3).
_NOT_FOUND = "Module not found."
_LOCKED = (
    "The mastery check opens once modules 1 to 5 are each complete or tested out with their "
    "quick check."
)
_NO_QUICK_CHECK = "This module has no quick check."
_QUICK_CHECK_TAKEN = (
    "You have taken this module's quick check. It is one try per module: work through the module "
    "to learn what it missed."
)
_ALREADY_DONE = "You have completed this module already, so there is nothing to test out of."
_ANSWERS_DONT_FIT = "Answer every question in the quick check, with one of its options."
_TOO_FAR = "Work through the module one segment at a time."
_RETRIEVAL_INCOMPLETE = "Answer the retrieval questions before starting this module."
_NOT_DONE = "Answer this segment's activity, or the video's checkpoints, before moving on."


@router.get("")
def list_modules(user: CurrentUser, session: DbSession) -> list[ModuleOut]:
    """All modules with the student's computed status and progress (FR-2).

    Returns every module in display order.  ``status`` is one of:
    ``locked | open | in_progress | complete``.  No commit needed — read-only."""
    return get_modules_for_user(session, user.id)


@router.get("/length")
def course_length(session: DbSession) -> CourseLengthOut:
    """The course's estimated length in minutes, the sum of every module's estimate. Public, so
    the register page can say how long the course takes with the same number the map shows."""
    return CourseLengthOut(minutes=course_minutes(session))


@router.get("/{module_id}")
def get_module(module_id: RowId, user: CurrentUser, session: DbSession) -> ModuleDetailOut:
    """One module with its full ordered segment list and the student's status.

    Returns 404 if the module does not exist; 403 if it is locked for this
    student (only the mastery check is: until modules 1 to 5 are complete or tested out)."""
    try:
        return get_module_detail(session, user.id, module_id)
    except ModuleNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND) from None
    except ModuleLocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=_LOCKED) from None
    except PositionTooFar:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=_TOO_FAR) from None


@router.post("/{module_id}/position")
def save_module_position(
    module_id: RowId, body: PositionIn, user: CurrentUser, session: DbSession
) -> ModuleDetailOut:
    """Record the student's current segment position and return the updated module.

    The client calls this whenever the student advances to a new segment.
    The furthest segment reached is kept, so stepping back changes nothing. A segment must be
    done (its activity answered, or its video's checkpoints passed) before moving past it, and
    saving the last segment again once it is done marks the module ``complete`` for good (saving
    it while it isn't done changes nothing).

    Returns the updated ``ModuleDetailOut`` so the frontend can re-render the
    module detail page with the new status in one round-trip (consistent with
    ``submit_attempt`` returning ``AttemptOut``).

    Returns 404 if the module does not exist; 403 if it is locked; 409 if the position is more
    than one segment past the furthest the student has reached, or past a segment they haven't
    done yet."""
    try:
        save_position(session, user.id, module_id, body.segment_position)
        session.commit()
        # Re-fetch the updated state so the response reflects the committed status.
        return get_module_detail(session, user.id, module_id)
    except ModuleNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND) from None
    except ModuleLocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=_LOCKED) from None
    except PositionTooFar:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=_TOO_FAR) from None
    except RetrievalIncomplete:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=_RETRIEVAL_INCOMPLETE) from None
    except SegmentNotDone:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=_NOT_DONE) from None


@router.get("/{module_id}/quick-check")
def get_quick_check(module_id: RowId, user: CurrentUser, session: DbSession) -> QuickCheckOut:
    """The module's quick check, "Already know this?" (FR-8.2, #214): its questions while this
    student may take it (no answers or hints are in them), or its result once taken. 404 for a
    module with no quick check (modules 0 and 6)."""
    try:
        return quick_check(session, user.id, module_id)
    except QuickCheckMissing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NO_QUICK_CHECK) from None


@router.post("/{module_id}/quick-check")
def take_quick_check(
    module_id: RowId, body: QuickCheckIn, user: CurrentUser, session: DbSession
) -> QuickCheckResultOut:
    """Mark the quick check: one answer for every question, sent together, marked at once
    (FR-8.2, #214). At most one wrong passes, and marks the module tested out; the result says
    what was missed and where to go next either way. One try per module: 409 once taken, or once
    the module is complete. 422 unless there is exactly one answer per question, each one of its
    options; nothing is recorded then. 404 for a module with no quick check."""
    try:
        result = take(
            session,
            user.id,
            module_id,
            [Answer(a.activity_id, a.selected) for a in body.answers],
        )
    except QuickCheckMissing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NO_QUICK_CHECK) from None
    except QuickCheckTaken:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=_QUICK_CHECK_TAKEN) from None
    except ModuleAlreadyDone:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=_ALREADY_DONE) from None
    except AnswersDontFit:
        raise HTTPException(422, detail=_ANSWERS_DONT_FIT) from None
    session.commit()
    return result
