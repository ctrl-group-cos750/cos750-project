"""Extra help for a struggling student: support segments per objective (FR-8.4, #172).

A module's segment may be **support** for one objective (`Segment.support_for`): a short worked
example, then one or two fresh practice items on that objective. The content puts a module's
support for an objective straight after the module's base practice for it. Everyone gets the base
segments; the support is shown only to a student who is struggling with that objective in that
module, and is shown once (ID document §5.2 and §7; the research is in the PR for #172: corrective
help in mastery learning, Bloom 1984 and Kulik, Kulik & Bangert-Drowns 1990; adaptive rather than
fixed fading, with a worked example before the next problem, Salden et al. 2010 and Renkl &
Atkinson 2003).

**The rule** (`struggling`, tuned by the constants below). Take the student's *first* attempts at
the objective's base practice items in this module, in the order they made them: the activities
shown by the module's segments that are not support, with purpose `practice` and that objective.
Retrieval, mastery and support items never count. The student is struggling once at least
`WRONG_TO_STRUGGLE` of any `WINDOW` first attempts in a row were wrong (2 of the last 3), or once
any of those first attempts was made after seeing hint `HINT_TO_STRUGGLE` or higher (hint 3 or 4,
which give most of the answer, FR-4.5). Until the student has answered enough base items for that,
the support isn't shown. "Once" is deliberate: the rule asks whether it was ever true, so a right
answer afterwards never takes back support that was already on offer.

**When it is decided.** A support segment is decided while it is still ahead of the student: while
the module is in progress and the segment is past the furthest one they have reached. Each time the
student saves a position, every support segment shown at that moment is recorded (`ShownSegment`),
and from then on it stays shown for good, even if a re-grade or a staff edit would now decide
otherwise. A support segment the student has already passed without it being shown stays hidden:
if the rule only fires after the student moved past the support (evidence from a base item placed
later in the module, or a student already past it when this was deployed), it is not shown behind
them, and not inserted ahead of them either. The help belongs next to the practice it explains; a
worked example for an earlier objective dropped into the middle of a later one would be out of
context, and the mastery check's review path (FR-7.5) is the corrective step for what is still
weak at the end. A complete module never gains support.

**Positions never shift.** Support segments stay in the module's list for everyone. One that is
hidden counts as done (FR-2.7), so the student moves straight past it (app/services/modules.py,
`save_position`), and the page skips it in Previous, Next and "Segment N of M".

Module 0's refreshers (FR-8.1, #31) are the same kind of thing the other way round: shown unless
the diagnostic rules them out. They can use the same mechanism: decide in `hidden_segments`,
record in `ShownSegment`, and the module service and the page already treat a hidden segment as
done and skipped.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, ModuleProgress, Segment, ShownSegment

# The rule (FR-8.4). Change it here: nothing else needs to know the numbers.
WINDOW = 3  # look at this many first attempts in a row ...
WRONG_TO_STRUGGLE = 2  # ... and this many of them wrong means struggling (2 of the last 3)
HINT_TO_STRUGGLE = 3  # a first attempt made after this hint level or higher means struggling


@dataclass(frozen=True)
class FirstAttempt:
    """A student's first attempt at one base practice item: whether it was right, and the
    highest hint level they had seen before sending it."""

    correct: bool
    hint_level: int


def struggling(first_attempts: Sequence[FirstAttempt]) -> bool:
    """Whether a student with these first attempts (in the order they were made) is struggling
    with the objective: at some point `WRONG_TO_STRUGGLE` of `WINDOW` first attempts in a row were
    wrong, or one was made after hint `HINT_TO_STRUGGLE` or higher. With too few attempts for
    either, not (yet)."""
    for index, attempt in enumerate(first_attempts):
        if attempt.hint_level >= HINT_TO_STRUGGLE:
            return True
        window = first_attempts[max(0, index - WINDOW + 1) : index + 1]
        if sum(not a.correct for a in window) >= WRONG_TO_STRUGGLE:
            return True
    return False


def _base_practice(
    session: Session, segments: Sequence[Segment], objectives: set[int]
) -> dict[int, int]:
    """The module's base practice items for these objectives: activity id -> objective."""
    shown = {
        s.activity_id
        for s in segments
        if s.kind == "activity" and s.activity_id is not None and s.support_for is None
    }
    if not shown or not objectives:
        return {}
    return {
        activity_id: objective_id
        for activity_id, objective_id in session.execute(
            select(Activity.id, Activity.objective_id).where(
                Activity.id.in_(shown),
                Activity.purpose == "practice",
                Activity.objective_id.in_(objectives),
            )
        )
        if objective_id is not None
    }


def struggling_objectives(
    session: Session, user_id: int, segments: Sequence[Segment], objectives: set[int]
) -> set[int]:
    """Which of these objectives this student is struggling with in the module whose segments
    these are (`struggling`, over their first attempts at its base practice items)."""
    base = _base_practice(session, segments, objectives)
    if not base:
        return set()
    firsts: dict[int, list[FirstAttempt]] = {}
    seen: set[int] = set()
    # In the order they were made: ids grow with time, and two at once are serialised per student
    # (app/services/locks.py), so the id order is the order the student answered in.
    for activity_id, correct, hint_level in session.execute(
        select(Attempt.activity_id, Attempt.correct, Attempt.hint_level)
        .where(Attempt.user_id == user_id, Attempt.activity_id.in_(base))
        .order_by(Attempt.id)
    ):
        if activity_id in seen:
            continue  # only the first attempt at each item counts
        seen.add(activity_id)
        firsts.setdefault(base[activity_id], []).append(FirstAttempt(bool(correct), hint_level))
    return {objective for objective, attempts in firsts.items() if struggling(attempts)}


def hidden_segments(
    session: Session, user_id: int, segments: Sequence[Segment], row: ModuleProgress | None
) -> set[int]:
    """The ids of this module's segments not shown to this student: the support segments
    (`Segment.support_for`) they don't need. `segments` is the module's whole list in order and
    `row` the student's progress in it (None before they open it).

    A support segment is shown if it was recorded as shown (`ShownSegment`), or if it is still
    ahead of the student in a module they haven't completed and they are struggling with its
    objective. Every other support segment is hidden."""
    support = [(index, s) for index, s in enumerate(segments) if s.support_for is not None]
    if not support:
        return set()
    recorded = set(
        session.scalars(
            select(ShownSegment.segment_id).where(
                ShownSegment.user_id == user_id,
                ShownSegment.segment_id.in_([s.id for _, s in support]),
            )
        )
    )
    deciding = row is None or row.status != "complete"
    furthest = row.current_segment_position if row is not None else 0
    ahead = {s.support_for for index, s in support if index > furthest and s.id not in recorded}
    live = (
        struggling_objectives(session, user_id, segments, {o for o in ahead if o is not None})
        if deciding and ahead
        else set()
    )
    return {
        s.id
        for index, s in support
        if s.id not in recorded and not (deciding and index > furthest and s.support_for in live)
    }


def record_shown(
    session: Session, user_id: int, segments: Sequence[Segment], hidden: Iterable[int]
) -> None:
    """Record every support segment of this module shown to the student now (not hidden), so it
    stays shown for good. Safe to repeat, and two at once can't record one twice."""
    hidden_ids = set(hidden)
    shown = [s.id for s in segments if s.support_for is not None and s.id not in hidden_ids]
    if not shown:
        return
    rows = [{"user_id": user_id, "segment_id": segment_id} for segment_id in shown]
    insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
    session.execute(insert(ShownSegment).values(rows).on_conflict_do_nothing())
    session.flush()
