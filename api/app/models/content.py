"""The course structure (SE document §8, FR-2): the learning objectives, the seven modules and the
ordered segments inside each module. All three are content: the fixtures in app/seed fill an empty
database, and staff edit it in the portal from then on (app/routers/staff_content.py). Never edited
by students.

`edited_at` is set when staff change a row in the portal. From then on the database's version is
the one that counts: the seed fills in what is missing and updates what nobody has edited, but
never writes over a staff edit (app/seed, `load`). `segments_edited_at` does the same for the
order and list of a module's (or an objective's review path's) segments.
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Objective(Base):
    """A learning objective, numbered as in the ID document (1 to 7; §3.1, Table 1). Mastery is
    decided per objective (FR-7), from the activities tagged with it."""

    __tablename__ = "objectives"

    id: Mapped[int] = mapped_column(primary_key=True)  # the objective's number
    text: Mapped[str] = mapped_column(Text)
    bloom_level: Mapped[str] = mapped_column(String(100))
    # The success criterion from the ID document's Table 1, in words, as the report shows it.
    criterion: Mapped[str] = mapped_column(Text)
    # The same criterion as the rule the mastery service evaluates (app/services/mastery.py),
    # counted over the parts of the module 6 items: at least `pass_fraction` of them right
    # ("at least 4 of 5" is 0.8), or at most `max_wrong` wrong ("with at most one error" is 1).
    # Exactly one is set; the seed checks that.
    pass_fraction: Mapped[float | None] = mapped_column()
    max_wrong: Mapped[int | None] = mapped_column()
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Its review path's segments (Segment.review_objective_id) were changed in the portal.
    segments_edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Module(Base):
    """One of the course's modules, 0 to 6 (ID document Table 4, FR-2.1). A module opens once the
    one before it is complete; module 0 is always open."""

    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(primary_key=True)  # the module's number, 0 to 6
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    # "By the end of this module you can …" (FR-2.3): one sentence per goal, in plain words.
    goals: Mapped[list[str]] = mapped_column(JSON)
    estimated_minutes: Mapped[int] = mapped_column()
    position: Mapped[int] = mapped_column()
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Its segments (which, and in what order) were changed in the portal.
    segments_edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Segment(Base):
    """One step of a module, or of an objective's review path, shown in `position` order (FR-2.2).

    A segment belongs to exactly one of the two: a module (`module_id`), or the review path of an
    objective (`review_objective_id`), which a student opens when the mastery check marks that
    objective "not yet" (FR-7.5, ID document §7.6).

    `kind` says what the step is: a narrated `video` (the Video row points here by `segment_id`,
    because videos are made by staff in the app, not in fixtures), Markdown `text`, a
    `worked_example`, an `activity` (`activity_id`), or a `refresher` that module 0's diagnostic
    can rule out (`refresher_for` names the diagnostic topic, FR-8.1). A segment with a
    `skip_check_activity_id` can be skipped by passing that activity (FR-8.2).

    A module's segment with `support_for` is support for that objective (FR-8.4, #172): a worked
    example or a fresh practice item that only a student struggling with the objective in this
    module is shown (app/services/support.py decides). It stays in the list for everyone, so
    positions never shift; for a student who doesn't need it, it is hidden and counts as done.
    """

    __tablename__ = "segments"
    __table_args__ = (
        CheckConstraint(
            "(module_id IS NULL) <> (review_objective_id IS NULL)", name="ck_segments_one_home"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int | None] = mapped_column(ForeignKey("modules.id"), index=True)
    review_objective_id: Mapped[int | None] = mapped_column(ForeignKey("objectives.id"), index=True)
    # Its place in the module or review path. The seed numbers segments in fixture order.
    position: Mapped[int] = mapped_column()
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="", server_default="")  # Markdown
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("activities.id"))
    skip_check_activity_id: Mapped[int | None] = mapped_column(ForeignKey("activities.id"))
    refresher_for: Mapped[str | None] = mapped_column(String(100))
    # The objective this is support for (FR-8.4): shown only to a student struggling with it.
    support_for: Mapped[int | None] = mapped_column(ForeignKey("objectives.id"))


class ObjectiveResult(Base):
    """A student's result on one objective (FR-7.2): `not_attempted`, `met_independently`,
    `met_with_support` or `not_yet`.

    Derived, never set by a client: app/services/mastery.py works it out from the student's
    attempts and rewrites this row after each mastery attempt and on every seed, so a changed rule
    is applied to everyone (FR-7.6). `evidence` is the ids of the attempts it was decided from.
    """

    __tablename__ = "objective_results"
    __table_args__ = (UniqueConstraint("user_id", "objective_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    objective_id: Mapped[int] = mapped_column(ForeignKey("objectives.id"))
    state: Mapped[str] = mapped_column(String(20))
    evidence: Mapped[list[int]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
