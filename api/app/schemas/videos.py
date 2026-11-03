"""A narrated video as the player needs it: where the media is, and where it stops (FR-3)."""

from app.schemas.activities import ActivityOut
from app.schemas.base import ApiModel


class CheckpointOut(ApiModel):
    """Where playback stops, and the activity to answer there. `passed` is true once this student
    has answered it correctly, so a returning student can seek past it (FR-3.5)."""

    id: int
    at_seconds: float
    passed: bool
    activity: ActivityOut


class VideoOut(ApiModel):
    """`mediaPath` and `captionsPath` are same-origin URLs under /media/. Checkpoints come in the
    order they are reached."""

    id: int
    title: str
    media_path: str
    captions_path: str
    transcript: str
    duration_seconds: int
    checkpoints: list[CheckpointOut]
