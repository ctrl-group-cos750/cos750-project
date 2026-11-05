from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Video(Base):
    """A narrated screen recording (SE document §8, FR-3). The MP4 and captions are static files
    under /media/, served by the web container; the API only knows their paths.

    §8 also links a video to its Segment. Segments arrive with the module player (#14, #15), so
    `segment_id` is added then.
    """

    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    media_path: Mapped[str] = mapped_column(String(300))
    captions_path: Mapped[str] = mapped_column(String(300))
    transcript: Mapped[str] = mapped_column(Text)  # Markdown: the text version of the video
    duration_seconds: Mapped[int] = mapped_column()


class Checkpoint(Base):
    """A point in a video where playback stops until the student answers an activity correctly
    (FR-3.3 to FR-3.5)."""

    __tablename__ = "checkpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True)
    at_seconds: Mapped[float] = mapped_column()
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"))
