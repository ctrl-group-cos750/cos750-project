"""Router for module-map and progress endpoints (SE document §9, FR-2).

All endpoints require an authenticated student (``CurrentUser``).  Every query is
scoped to ``user.id`` — never touches another student's data (NFR-S2, FR-1.3).

Endpoints
---------
GET  /api/modules                       → list[ModuleOut]
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
from app.schemas.modules import ModuleDetailOut, ModuleOut, PositionIn
from app.services.modules import (
    ModuleLocked,
    ModuleNotFound,
    PositionTooFar,
    RetrievalIncomplete,
    get_module_detail,
    get_modules_for_user,
    save_position,
)

router = APIRouter(prefix="/api/modules", tags=["modules"])

# Student-friendly error messages (NFR-U3).
_NOT_FOUND = "Module not found."
_LOCKED = "This module is not available yet. Complete the previous module to unlock it."
_TOO_FAR = "Work through the module one segment at a time."
_RETRIEVAL_INCOMPLETE = "Answer the retrieval questions before starting this module."


@router.get("")
def list_modules(user: CurrentUser, session: DbSession) -> list[ModuleOut]:
    """All modules with the student's computed status and progress (FR-2).

    Returns every module in display order.  ``status`` is one of:
    ``locked | open | in_progress | complete``.  No commit needed — read-only."""
    return get_modules_for_user(session, user.id)


@router.get("/{module_id}")
def get_module(module_id: int, user: CurrentUser, session: DbSession) -> ModuleDetailOut:
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
    module_id: int, body: PositionIn, user: CurrentUser, session: DbSession
) -> ModuleDetailOut:
    """Record the student's current segment position and return the updated module.

    The client calls this whenever the student advances to a new segment.
    The furthest segment reached is kept, so stepping back changes nothing. Reaching the last
    segment marks the module ``complete`` for good.

    Returns the updated ``ModuleDetailOut`` so the frontend can re-render the
    module detail page with the new status in one round-trip (consistent with
    ``submit_attempt`` returning ``AttemptOut``).

    Returns 404 if the module does not exist; 403 if it is locked; 409 if the position is more
    than one segment past the furthest the student has reached."""
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
