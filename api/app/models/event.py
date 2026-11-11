from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Event(Base):
    """Something a student did or that happened to them, with when (SE document §8, FR-10.1).
    Append-only: the pilot's timeline for the ID team's evaluation (ID document §8).

    `type` is one of `app.services.events.EVENT_TYPES`; `ref` names what it was about
    (`video:3`, `checkpoint:12`, `activity:301`, `objective:5`); `payload` holds the few details
    that type has (a hint's level, a result's old and new state). Exported by internal id only.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    ref: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
