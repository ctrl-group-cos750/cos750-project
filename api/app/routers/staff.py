from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select

from app.auth import StaffUser
from app.db import DbSession
from app.media import KINDS, MediaError, file_for, save_upload
from app.models import Checkpoint, User, Video
from app.schemas.staff import (
    MediaOut,
    StaffMemberIn,
    StaffMemberOut,
    StaffVideoIn,
    StaffVideoOut,
    StaffVideoSummary,
)
from app.services.videos import UnknownCheckpoint, save_video, video_for_editor

# Team members only (users.is_staff). A team member grants it to another on the staff portal's
# "Staff members" page; `python -m app.staff grant <email>` makes the first one.
router = APIRouter(prefix="/api/staff", tags=["staff"])

NOT_FOUND = "This video does not exist."


@router.post("/media", status_code=status.HTTP_201_CREATED)
async def upload_media(
    request: Request, _staff: StaffUser, kind: Literal["video", "captions"]
) -> MediaOut:
    """Upload one file to the media volume. Send the raw file as the body, with
    `Content-Type: video/mp4` and `?kind=video`, or `Content-Type: text/vtt` and `?kind=captions`.
    Returns the `/media/…` path to put in the video. Up to 95 MB for a video, 1 MB for captions.

    The exact Content-Type is required: a cross-site form can't send these types, so another
    site can't make a logged-in team member's browser upload files."""
    spec = KINDS[kind]
    sent = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if sent != spec.content_type:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Send the file with Content-Type: {spec.content_type}.",
        )
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > spec.max_bytes:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"The file is over {spec.max_bytes // (1024 * 1024)} MB. Compress it first.",
        )
    try:
        path, size = await save_upload(kind, request.stream())
    except MediaError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return MediaOut(path=path, bytes=size)


@router.get("/videos")
def list_videos(session: DbSession, _staff: StaffUser) -> list[StaffVideoSummary]:
    """Every video, newest first, with how many checkpoints each has."""
    counts = (
        select(Checkpoint.video_id, func.count().label("n"))
        .group_by(Checkpoint.video_id)
        .subquery()
    )
    rows = session.execute(
        select(Video, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.video_id == Video.id)
        .order_by(Video.id.desc())
    ).all()
    return [
        StaffVideoSummary(
            id=v.id, title=v.title, duration_seconds=v.duration_seconds, checkpoint_count=n
        )
        for v, n in rows
    ]


def _check_media_exists(data: StaffVideoIn) -> None:
    for label, path in (("video", data.media_path), ("captions", data.captions_path)):
        if not file_for(path).is_file():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"The {label} file {path} is not on the media volume. Upload it again.",
            )


@router.post("/videos", status_code=status.HTTP_201_CREATED)
def create_video(data: StaffVideoIn, session: DbSession, _staff: StaffUser) -> StaffVideoOut:
    """Create a video with its checkpoints (leave out checkpoint ids). Students see it at
    `GET /api/videos/{id}`."""
    _check_media_exists(data)
    if any(c.id is not None for c in data.checkpoints):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="A new video has no checkpoint ids yet."
        )
    video = Video()
    save_video(session, video, data)
    return video_for_editor(session, video)


@router.get("/videos/{video_id}")
def get_video_for_editor(video_id: int, session: DbSession, _staff: StaffUser) -> StaffVideoOut:
    """The video with every checkpoint's question, correct option, feedback and hints."""
    video = session.get(Video, video_id)
    if video is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return video_for_editor(session, video)


@router.put("/videos/{video_id}")
def update_video(
    video_id: int, data: StaffVideoIn, session: DbSession, _staff: StaffUser
) -> StaffVideoOut:
    """Replace the video and its checkpoint list. Keep each existing checkpoint's `id` so its
    attempts stay linked; a checkpoint left out is removed."""
    video = session.get(Video, video_id)
    if video is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    _check_media_exists(data)
    try:
        save_video(session, video, data)
    except UnknownCheckpoint as exc:
        session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return video_for_editor(session, video)


NO_ACCOUNT = "No account uses this email. They need to register in the app first."
NOT_A_MEMBER = "This person is not a team member."
NOT_YOURSELF = "You can't remove your own access. Ask another team member to do it."


@router.get("/members")
def list_members(session: DbSession, _staff: StaffUser) -> list[StaffMemberOut]:
    """Every team member, by name."""
    users = session.scalars(select(User).where(User.is_staff).order_by(User.display_name, User.id))
    return [StaffMemberOut.model_validate(u) for u in users]


@router.post("/members")
def add_member(data: StaffMemberIn, session: DbSession, _staff: StaffUser) -> StaffMemberOut:
    """Make the account with this email a team member. It must exist already. Someone who is
    staff already stays staff (no error), so pressing the button twice is harmless."""
    user = session.scalar(select(User).where(User.email == data.email))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NO_ACCOUNT)
    user.is_staff = True
    session.commit()
    return StaffMemberOut.model_validate(user)


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(user_id: int, session: DbSession, staff: StaffUser) -> None:
    """Take staff access away. It ends at once: every request reads `is_staff` afresh. Nobody can
    remove themselves, so the portal always has at least one team member left."""
    if user_id == staff.id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=NOT_YOURSELF)
    user = session.get(User, user_id)
    if user is None or not user.is_staff:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_A_MEMBER)
    user.is_staff = False
    session.commit()
