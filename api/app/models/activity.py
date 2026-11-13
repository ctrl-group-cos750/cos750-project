from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
)
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
    # Where the activity sits and what it is evidence for (FR-4.3). All three come from the content
    # fixtures; an activity made in the staff video editor has no module or objective yet.
    module_id: Mapped[int | None] = mapped_column(ForeignKey("modules.id"), index=True)
    objective_id: Mapped[int | None] = mapped_column(ForeignKey("objectives.id"), index=True)
    # practice | diagnostic | retrieval | mastery | review | bonus (app/schemas/content.py)
    purpose: Mapped[str] = mapped_column(String(32), default="practice", server_default="practice")
    # Set when staff change it (or its hints) in the portal; the seed never writes over it then.
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
    # The highest hint level this student had seen on this activity before submitting (FR-4.5).
    # 3 or 4 makes a correct answer count as "met with support" (FR-7.2).
    hint_level: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Hint(Base):
    """One rung of an activity's four-level hint ladder (SE document §8, FR-4.4). Level 4 is the
    worked solution, so hints are only sent one at a time, after the student asks."""

    __tablename__ = "hints"
    __table_args__ = (UniqueConstraint("activity_id", "level"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), index=True)
    level: Mapped[int] = mapped_column()
    body: Mapped[str] = mapped_column(Text)


class HintView(Base):
    """A student was shown a hint (FR-4.4, FR-4.5). Append-only. The next hint a student gets, and
    the `hint_level` stored on their next attempt, both come from these rows."""

    __tablename__ = "hint_views"
    # Each level once per student and activity (#138): the lock in app/services/locks.py stops two
    # requests from both revealing it; this is the database's guarantee.
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "activity_id",
            "level",
            "round",
            name="hint_views_user_id_activity_id_level_round_key",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), index=True)
    level: Mapped[int] = mapped_column()
    # Which time through the module (0, then one more for each restart): a restarted module shows
    # its hints again from level 1, so each level is once per round (app/services/restart.py).
    round: Mapped[int] = mapped_column(default=0, server_default="0")
    # The newest attempt id (anyone's) when the hint was shown. Attempts are append-only and both
    # are written under the student's lock, so this hint came before exactly this student's
    # attempts with a higher id: hint 3 or 4 only makes those "with support" (rewards.py), never an
    # answer already given, even after a restart (#211 review).
    after_attempt: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
