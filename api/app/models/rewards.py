from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PointsRule(Base):
    """How many points one kind of event is worth (SE document FR-9.1, FR-9.2). Seeded by the
    migration with the values in the SE document's table; change a row to retune the points
    without a code change."""

    __tablename__ = "points_rules"

    event: Mapped[str] = mapped_column(String(40), primary_key=True)
    points: Mapped[int] = mapped_column()


class PointsEntry(Base):
    """Points a student earned (FR-9.1). Append-only, and never negative: nothing a student does
    takes points away. A student's total is the sum.

    `ref` says what the points were for ("activity:12", "objective:5"), and a student earns each
    `ref` once, so answering the same activity again earns nothing more.
    """

    __tablename__ = "points_entries"
    __table_args__ = (UniqueConstraint("user_id", "ref"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event: Mapped[str] = mapped_column(String(40))
    ref: Mapped[str] = mapped_column(String(80))
    points: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserBadge(Base):
    """A badge a student earned (FR-9.3). Never deleted: a badge, once earned, stays.

    `badge` is an id from the catalogue (app/services/rewards.py, and web/src/components/
    achievements.ts for its name and picture). `ref` tells apart badges a student can earn more
    than once, such as one per bonus quest; it is "" otherwise. Objective badges have a `tier`,
    their level: "practised" (secure in practice), "bronze" (met with support) or "gold" (met
    independently). It only goes up that list, never down.
    """

    __tablename__ = "user_badges"
    __table_args__ = (UniqueConstraint("user_id", "badge", "ref"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    badge: Mapped[str] = mapped_column(String(40))
    ref: Mapped[str] = mapped_column(String(40), default="", server_default="")
    tier: Mapped[str | None] = mapped_column(String(10))
    awarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    upgraded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When the student was shown it. Null means new: the app announces it, then marks it seen.
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
