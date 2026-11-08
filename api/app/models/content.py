"""The course structure (SE document §8, FR-2): the learning objectives, the seven modules and the
ordered segments inside each module. All three are content, loaded from the fixtures in app/seed,
never edited by students.
"""

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Objective(Base):
    """A learning objective, numbered as in the ID document (1 to 7; §3.1, Table 1). Mastery is
    decided per objective (FR-7), from the activities tagged with it."""

    __tablename__ = "objectives"

    id: Mapped[int] = mapped_column(primary_key=True)  # the objective's number
    text: Mapped[str] = mapped_column(Text)
    bloom_level: Mapped[str] = mapped_column(String(100))
    # The success criterion from the ID document's Table 1, in words. The mastery service (#22)
    # turns it into the rule it evaluates.
    criterion: Mapped[str] = mapped_column(Text)


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


class Segment(Base):
    """One step of a module, shown in `position` order (FR-2.2).

    `kind` says what the step is: a narrated `video` (the Video row points here by `segment_id`,
    because videos are made by staff in the app, not in fixtures), Markdown `text`, a
    `worked_example`, an `activity` (`activity_id`), or a `refresher` that module 0's diagnostic
    can rule out (`refresher_for` names the diagnostic topic, FR-8.1). A segment with a
    `skip_check_activity_id` can be skipped by passing that activity (FR-8.2).
    """

    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id"), index=True)
    # Its place in the module. The seed numbers segments in fixture order, so no two collide.
    position: Mapped[int] = mapped_column()
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="", server_default="")  # Markdown
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("activities.id"))
    skip_check_activity_id: Mapped[int | None] = mapped_column(ForeignKey("activities.id"))
    refresher_for: Mapped[str | None] = mapped_column(String(100))
