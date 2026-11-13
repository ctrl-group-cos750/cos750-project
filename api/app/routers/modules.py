"""Router for module-map and progress endpoints (SE document §9, FR-2).

All endpoints but ``/length`` require an authenticated student (``CurrentUser``).  Every query is
scoped to ``user.id`` — never touches another student's data (NFR-S2, FR-1.3).

Endpoints
---------
GET  /api/modules                       → list[ModuleOut]
GET  /api/modules/length                → CourseLengthOut  (public: the register page shows it)
GET  /api/modules/{module_id}           → ModuleDetailOut
POST /api/modules/{module_id}/position  → ModuleDetailOut  (body: PositionIn)

Error mapping
-------------
``ModuleNotFound`` (service) → 404  "Module not found."
``ModuleLocked``   (service) → 403  "This module is not available yet.
                                      Complete the previous module to unlock it."
``PositionTooFar`` (service) → 409  "Work through the module one segment at a time."
"""

from fastapi import APIRouter, HTTPException, status

from app.auth import CurrentUser
from app.db import DbSession
from app.schemas.ids import RowId
from app.schemas.modules import CourseLengthOut, ModuleDetailOut, ModuleOut, PositionIn
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
from app.services.restart import CannotRestart, restart_module

router = APIRouter(prefix="/api/modules", tags=["modules"])

# Student-friendly error messages (NFR-U3).
_NOT_FOUND = "Module not found."
_LOCKED = "This module is not available yet. Complete the previous module to unlock it."
_TOO_FAR = "Work through the module one segment at a time."
_RETRIEVAL_INCOMPLETE = "Answer the retrieval questions before starting this module."
_NOT_DONE = "Answer this segment's activity, or the video's checkpoints, before moving on."
_CANNOT_RESTART = (
    "This module can't be restarted until you have finished it. The mastery check can't be "
    "restarted either, because only your first answer counts there; your report's review paths "
    "are the way to practise again."
)


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
    student (the previous module has not been completed yet)."""
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


@router.post(
    "/{module_id}/restart",
    responses={409: {"description": "The mastery check, or a module not started yet."}},
)
def restart(module_id: RowId, user: CurrentUser, session: DbSession) -> ModuleDetailOut:
    """Start the module again to redo its questions (app/services/restart.py): it opens at its
    start, and every question, retrieval question and video checkpoint in it shows unanswered,
    with hints from level 1 again. The module stays complete and earned points and badges stay;
    earlier answers stay recorded for the evaluation but aren't shown. 404 if there is no such
    module, 403 while it is locked, 409 for the mastery check or a module not started."""
    try:
        get_module_detail(session, user.id, module_id)  # 404 or 403 first
        restart_module(session, user.id, module_id)
        session.commit()
        return get_module_detail(session, user.id, module_id)
    except ModuleNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND) from None
    except ModuleLocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=_LOCKED) from None
    except CannotRestart:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=_CANNOT_RESTART) from None
