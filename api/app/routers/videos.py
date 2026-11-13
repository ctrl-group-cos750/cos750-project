from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.auth import CurrentUser
from app.db import DbSession
from app.models import Activity, Attempt, Checkpoint, Segment, Video
from app.schemas.activities import ActivityOut
from app.schemas.ids import RowId
from app.schemas.videos import CheckpointOut, VideoOut
from app.services.access import video_refusal
from app.services.restart import module_round

router = APIRouter(prefix="/api/videos", tags=["videos"])

NOT_FOUND = "This video does not exist."
MODULE_LOCKED = (
    "This video is in a module that isn't open yet. Complete the module before it to unlock it."
)
LOCKED = "This video is in a part of the course that isn't open yet."


@router.get("/{video_id}")
def get_video(video_id: RowId, user: CurrentUser, session: DbSession) -> VideoOut:
    """Everything the player needs in one call (FR-3): media and captions paths, the transcript,
    and each checkpoint with its activity (without the answer) and whether this student has
    passed it (since the module's restart, if they restarted it). Answer a checkpoint with
    `POST /api/activities/{activityId}/attempts`.

    403 while the segment that plays the video is in a locked module or a closed review path
    (#137); a video on no segment yet is open. Its checkpoint questions follow the video."""
    video = session.get(Video, video_id)
    if video is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    # Its checkpoints stay unseen too (FR-2.1). Staff are let through, so the video editor's
    # "Open as a student" works on any video.
    refusal = video_refusal(session, user, video)
    if refusal is not None:
        detail = MODULE_LOCKED if refusal == "module_locked" else LOCKED
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=detail)
    rows = session.execute(
        select(Checkpoint, Activity)
        .join(Activity, Activity.id == Checkpoint.activity_id)
        .where(Checkpoint.video_id == video.id)
        .order_by(Checkpoint.at_seconds, Checkpoint.id)
    ).all()
    # Passed in this round of the module that plays it: after a restart every checkpoint asks
    # again, as the module page's "done" expects (app/services/restart.py, #211 review).
    module_id = (
        session.scalar(select(Segment.module_id).where(Segment.id == video.segment_id))
        if video.segment_id is not None
        else None
    )
    after = module_round(session, user.id, module_id).after
    passed_query = select(Attempt.activity_id).where(
        Attempt.user_id == user.id,
        Attempt.correct.is_(True),
        Attempt.activity_id.in_([activity.id for _, activity in rows]),
    )
    if after is not None:
        passed_query = passed_query.where(Attempt.id > after)
    passed = set(session.scalars(passed_query))
    return VideoOut(
        id=video.id,
        title=video.title,
        media_path=video.media_path,
        captions_path=video.captions_path,
        transcript=video.transcript,
        duration_seconds=video.duration_seconds,
        checkpoints=[
            CheckpointOut(
                id=checkpoint.id,
                at_seconds=checkpoint.at_seconds,
                passed=activity.id in passed,
                activity=ActivityOut.model_validate(activity),
            )
            for checkpoint, activity in rows
        ],
    )
