from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Module(Base):
    """One unit of the course a student works through sequentially (SE document §8, FR-2.1, FR-2.3).

    Module 0 is always open (warm-up and diagnostic). Modules 1-5 unlock when the previous module
    is complete. Module 6 is the mastery check. `goals` holds the 'By the end of this module you
    can ...' text shown at the top of every module page (FR-2.3).
    """

    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 0 to 6, matching the seven modules in the ID document.
    number: Mapped[int] = mapped_column()
    slug: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String(200))
    goals: Mapped[str] = mapped_column(Text)  # Markdown: "By the end of this module you can …"
    estimated_minutes: Mapped[int] = mapped_column()
    # Defines the display order when listing modules on the map.
    position: Mapped[int] = mapped_column()


class Segment(Base):
    """One step inside a module (SE document §8, FR-2.1, FR-2.5).

    A segment is one of five kinds:
    - `video`         — plays a narrated screen recording (see Video.segment_id).
    - `text`          — displays `body` as rendered Markdown.
    - `worked_example`— displays `body` as rendered Markdown (detailed walkthrough).
    - `activity`      — presents an interactive activity (see `activity_id`).
    - `refresher`     — an optional remedial segment the diagnostic can prescribe (FR-8.1).

    Decision 1 (approved): Segment owns `video_id` and `activity_id` FKs so the module page can
    load a segment and its content in one query. Video also carries `segment_id` (the other
    direction) as the SE §8 ER diagram shows.
    """

    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id"), index=True)
    # 0-based display order within the module.
    position: Mapped[int] = mapped_column()
    # One of: video | text | worked_example | activity | refresher
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    # Markdown body — populated for `text` and `worked_example` segments; null for others.
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Passing this activity lets the student skip the segment (FR-8.2). Nullable.
    skip_check_activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("activities.id"), nullable=True
    )
    # The diagnostic topic that makes a refresher segment required (FR-8.1). Nullable.
    refresher_for: Mapped[str | None] = mapped_column(String, nullable=True)
    # FK to the video this segment plays — populated for `video` segments only.
    video_id: Mapped[int | None] = mapped_column(ForeignKey("videos.id"), nullable=True)
    # FK to the activity this segment presents — populated for `activity` segments only.
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("activities.id"), nullable=True)


class ModuleProgress(Base):
    """A student's progress through one module (SE document §8, FR-2.5, FR-2.6).

    Decision 5 (approved): surrogate `id` primary key + UniqueConstraint on (user_id, module_id),
    matching the convention every other table uses. `status` transitions:
    open → in_progress → complete.

    `current_segment_position` records the 0-based position of the last segment the student
    reached, so the module page can resume from the right place (FR-2.5).
    """

    __tablename__ = "module_progress"
    __table_args__ = (UniqueConstraint("user_id", "module_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id"), index=True)
    # One of: open | in_progress | complete
    status: Mapped[str] = mapped_column(String(20), default="open", server_default="open")
    # 0-based index of the segment the student is currently on (FR-2.5).
    current_segment_position: Mapped[int] = mapped_column(default=0, server_default="0")
    # Set when the student reaches the last segment and advances (FR-2.6).
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
