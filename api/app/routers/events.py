from fastapi import APIRouter, HTTPException, Response, status
from pydantic import Field

from app.auth import CurrentUser
from app.db import DbSession
from app.rate_limit import RateLimiter
from app.schemas.base import ApiModel
from app.schemas.ids import DB_INT_MAX
from app.services.events import ClientEvent, log_client_event
from app.services.modules import segment_locked

router = APIRouter(prefix="/api/events", tags=["events"])

# A student watching a video sends a few events a minute; this only stops a runaway loop or a
# script from filling the log.
events_limiter = RateLimiter(limit=120, window=60)


class EventIn(ApiModel):
    """What the browser saw: `video_started` or `video_completed` (`targetId` is the video),
    `checkpoint_reached` (the checkpoint) or `segment_viewed` (the segment)."""

    type: ClientEvent
    target_id: int = Field(gt=0, le=DB_INT_MAX)


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
def report_event(body: EventIn, user: CurrentUser, session: DbSession) -> Response:
    """Log something only the browser sees, for the pilot's evaluation (FR-10.1). The server adds
    who and when. 404 if the video, checkpoint or segment doesn't exist; 429 past 120 a minute. A
    segment viewed in a module still locked for the student is accepted but not logged."""
    events_limiter.check(f"user:{user.id}")
    # A segment in a module still locked for this student can't have been viewed: it is noise in
    # the pilot log, so it is accepted (nothing for the browser to handle) but not logged (#166).
    if body.type == "segment_viewed" and segment_locked(session, user.id, body.target_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    try:
        log_client_event(session, user.id, body.type, body.target_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
