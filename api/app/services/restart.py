"""Restarting a module to redo its questions.

A student who finished a module can go through it again without their earlier answers on screen:
every question, retrieval question and video checkpoint in it shows unanswered, and its hints start
again from level 1. Nothing is taken away. The module stays complete (so the modules after it stay
open), and the points and badges already earned stay, because each is only ever awarded once
(app/services/rewards.py). Nothing is deleted either: every earlier attempt and hint stays in the
evaluation data (FR-10), and the restart itself is logged.

How: `ModuleProgress.restarted_after_attempt` holds the newest attempt id at the restart, and the
module page, its activities, their hints and its videos' checkpoints only count attempts after it
(`after`). Hint views carry a `round`, one more each time the module is restarted, so each hint
level is still shown once per round, and the newest attempt id when shown (`after_attempt`), so
hint 3 or 4 counts against a later answer (even one after a restart) but never an earlier one.

For the evaluation, rounds are recovered from the data alone: the hints CSV has each view's
`round`, and each `module_restarted` event carries its `round` and `after_attempt`, so a student's
attempts at the module's activities between two restarts' `after_attempt` are that round's.

The mastery check (module 6) can't be restarted: only a student's first answer counts there
(FR-7.1), so redoing it would change nothing they could see, and the review paths are the way to
practise an objective again.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Checkpoint, ModuleProgress, Segment, Video
from app.services.events import log_event
from app.services.locks import lock_student
from app.services.mastery import MASTERY_MODULE


class CannotRestart(ValueError):
    """The module can't be restarted: the mastery check, or one the student hasn't worked through
    to the end (only tested out of, FR-8.2, counts as not finished)."""


@dataclass(frozen=True)
class Round:
    """Which time through a module: attempts with an id above `after` (None for all), and hints
    of round `number`."""

    after: int | None = None
    number: int = 0


FIRST = Round()


def _progress(session: Session, user_id: int, module_id: int) -> ModuleProgress | None:
    return session.scalar(
        select(ModuleProgress).where(
            ModuleProgress.user_id == user_id, ModuleProgress.module_id == module_id
        )
    )


def module_round(session: Session, user_id: int, module_id: int | None) -> Round:
    """This student's current round in the module: FIRST if they never restarted it."""
    if module_id is None:
        return FIRST
    row = _progress(session, user_id, module_id)
    if row is None or row.restarted_after_attempt is None:
        return FIRST
    return Round(after=row.restarted_after_attempt, number=row.restarts)


def module_of(session: Session, activity: Activity) -> int | None:
    """The module an activity is shown in: its own, or, for a video checkpoint's question (made in
    the video editor, with no module), the module of the segment that plays the video. None for a
    review path's items, which belong to an objective and are never restarted."""
    if activity.module_id is not None:
        return activity.module_id
    return session.scalar(
        select(Segment.module_id)
        .join(Video, Video.segment_id == Segment.id)
        .join(Checkpoint, Checkpoint.video_id == Video.id)
        .where(Checkpoint.activity_id == activity.id)
        .limit(1)
    )


def activity_round(session: Session, user_id: int, activity: Activity) -> Round:
    """The student's current round for the module this activity is shown in."""
    return module_round(session, user_id, module_of(session, activity))


def restart_module(session: Session, user_id: int, module_id: int) -> ModuleProgress:
    """Start the module again for this student (not committed). Raises `CannotRestart` for the
    mastery check or a module they haven't finished. Takes the student's write lock, so an answer
    in flight lands either before the restart or after it, never half in each."""
    if module_id == MASTERY_MODULE:
        raise CannotRestart(module_id)
    lock_student(session, user_id)
    row = session.scalar(
        select(ModuleProgress)
        .where(ModuleProgress.user_id == user_id, ModuleProgress.module_id == module_id)
        .with_for_update()
    )
    if row is None or row.status != "complete":
        # Only a finished module: restarting one part-way through would lose the student's place
        # and its progress on the map (13 Nov audit). A module only tested out of (`tested_out`,
        # FR-8.2) has not been worked through, so there is nothing to redo yet: the student works
        # through it, which completes it, and may restart it then. A restart never reopens the
        # quick check, which is one try per module.
        raise CannotRestart(module_id)
    row.restarted_at = datetime.now(tz=UTC)
    row.restarted_after_attempt = session.scalar(select(func.max(Attempt.id))) or 0
    row.restarts += 1
    row.current_segment_position = 0
    # Every restart's boundary stays in the event log (the row keeps only the latest): attempts at
    # this module's activities with an id above one restart's `after_attempt`, and not above the
    # next one's, are that round's (FR-10).
    log_event(
        session,
        user_id,
        "module_restarted",
        f"module:{module_id}",
        {"round": row.restarts, "after_attempt": row.restarted_after_attempt},
    )
    session.flush()
    return row
