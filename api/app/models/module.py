from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ModuleProgress(Base):
    """A student's progress through one module (SE document §8, FR-2.5, FR-2.6). The modules and
    their segments are content (app/models/content.py); this is the only part a student writes.

    `current_segment_position` is the furthest segment the student has reached, 0-based. It never
    goes down, so stepping back to reread a segment loses nothing, and the module page resumes
    where the student got to. A student can only move one segment past it at a time, so a module
    can't be finished by jumping to its end.

    `status` is `in_progress` until the student reaches the last segment, then `complete` for
    good: going back afterwards never re-locks the module after it (FR-2.1). There is no row until
    the student first opens the module.
    """

    __tablename__ = "module_progress"
    __table_args__ = (UniqueConstraint("user_id", "module_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    current_segment_position: Mapped[int] = mapped_column(default=0, server_default="0")
    # When the student first reached the last segment (FR-2.6).
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
