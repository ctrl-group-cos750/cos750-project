from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.auth import CurrentUser
from app.db import DbSession
from app.models import Activity, Attempt, Checkpoint, Video
from app.schemas.activities import ActivityOut
from app.schemas.videos import CheckpointOut, VideoOut

router = APIRouter(prefix="/api/videos", tags=["videos"])

NOT_FOUND = "This video does not exist."


@router.get("/{video_id}")
def get_video(video_id: int, user: CurrentUser, session: DbSession) -> VideoOut:
    """Everything the player needs in one call (FR-3): media and captions paths, the transcript,
    and each checkpoint with its activity (without the answer) and whether this student has
    passed it. Answer a checkpoint with `POST /api/activities/{activityId}/attempts`."""
    video = session.get(Video, video_id)
    if video is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    rows = session.execute(
        select(Checkpoint, Activity)
        .join(Activity, Activity.id == Checkpoint.activity_id)
        .where(Checkpoint.video_id == video.id)
        .order_by(Checkpoint.at_seconds, Checkpoint.id)
    ).all()
    passed = set(
        session.scalars(
            select(Attempt.activity_id).where(
                Attempt.user_id == user.id,
                Attempt.correct.is_(True),
                Attempt.activity_id.in_([activity.id for _, activity in rows]),
            )
        )
    )
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
