from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Activity(Base):
    """One activity a student answers (SE document §8, FR-4, FR-5).

    `config` is what the student is shown (for a code activity: the lines to order, or the code
    with blanks and the token choices). `solution` is server-only — the correct order or tokens —
    and is never put in a response (see app/schemas/activities.py and the checker). Code activities
    run no student code: they are graded by comparing a submission with `solution` (NFR-S7).
    """

    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    # Visible activities may show why an answer is wrong; hidden ones show only generic messages.
    visible: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    solution: Mapped[dict[str, Any]] = mapped_column(JSON)


class Attempt(Base):
    """A student's submission to an activity and how it was graded (SE document §8, FR-5.3).

    Append-only: one row per submission. `submitted` holds only the student's choices (line ids,
    chosen tokens), never free-form code. `detail` holds the per-part result shown back.
    """

    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), index=True)
    submitted: Mapped[dict[str, Any]] = mapped_column(JSON)
    correct: Mapped[bool] = mapped_column(Boolean)
    score: Mapped[float] = mapped_column()
    detail: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
