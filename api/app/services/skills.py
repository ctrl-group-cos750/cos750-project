"""The skill profile and module medals (SE document FR-9.7, FR-9.8; issue #214).

Both are read from attempts on each request, like the mastery report, and store nothing.

**Skill profile.** One entry per learning objective. Before the mastery check has a result it
shows practice progress as one of three coarse levels, not a percentage of a handful of answers:

- **not started**: none of the objective's practice items answered yet,
- **practising**: some answered,
- **secure**: every one answered, and at least 80% of them right without hint 3 or 4 (the
  same line as the ID document's typical criterion, "at least 4 of 5").

The counts behind the level are sent too, for the profile to show on request. Practice items are
the module activities tagged with the objective whose purpose is practice or retrieval, that every
student meets on the way through a module: on a module segment that is not extra support (FR-8.4),
a module's own retrieval question, or a video checkpoint's question. Bonus quests (optional), skip
checks, support-only items, review-path items and mastery items are left out, so the total is one
every student can reach and the profile never gives away the check. Once the mastery check (or a
review path) has given the objective a result, `result` carries it, and the profile shows gold
(met independently), bronze (met with support) or not yet.

**Module medals.** A finished module earns a medal for how well its activities were mastered,
never for effort or speed. Each activity the module asks every student to answer (as above;
module 0's diagnostic finds gaps rather than marking, so it isn't one) is:

- *first time* if the student's first answer to it was right without hint 3 or 4,
- *on your own* if some answer to it was right without hint 3 or 4 (FR-7.2 and FR-9.2's line).

Then (`medal_for`, the one place the rule lives):

- **gold**: every activity right first time,
- **silver**: every activity right on your own,
- **bronze**: the module finished with at least one activity right on your own,
- **none**: the module finished without one (every answer wrong, moved on after two tries): the
  same line as the module's points and First Module badge (app/services/modules.py
  `reward_module`), so walking through a module earns nothing (#215 review).

A module the student worked through to the end is judged on the activities they answered on the
way. An activity added to it afterwards isn't one they were asked, so it can't lower the medal they
finished with (review of #223, Must fix 2: module 1's warm-up question left the medal set and a
graph-words item joined it, and every finished student's gold became bronze). Working through a
module answers every activity it asks for, so for anyone who finished it since, that is all of
them.

A module whose quick check the student passed earns silver: the check showed the student can do
it on their own, but not every activity was answered. That stays when the student works through
the module afterwards: more work never lowers a medal, so they get the better of the two
(`quick_check.passed` is read from the check's answers, not from the module's status, which
becomes "complete"). A module with nothing to mark (module 0's
diagnostic, module 6's mastery check, whose results are the report) has no medal. While a module
is in progress, `heading_for` is the medal the answers so far are on course for, counting only
activities already answered.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Checkpoint, Module, ModuleProgress, Segment
from app.services import quick_check
from app.services.mastery import MASTERY_MODULE, State, evaluate
from app.services.rewards import SUPPORT_LEVEL

Medal = Literal["gold", "silver", "bronze"]

# The purposes that count as practice for the skill profile and for a module's medal.
PRACTICE_PURPOSES: frozenset[str] = frozenset({"practice", "retrieval"})


Level = Literal["not_started", "practising", "secure"]

# Share of an objective's practice items right without hint 3 or 4 that makes it secure.
SECURE_SHARE = 0.8


@dataclass(frozen=True)
class Skill:
    objective_id: int
    text: str
    answered: int  # practice items answered at all
    correct: int  # answered right at some point
    on_your_own: int  # answered right without hint 3 or 4
    total: int
    level: Level
    result: State | None  # None until the mastery check (or a review path) decides it


@dataclass(frozen=True)
class ModuleMedal:
    module_id: int
    complete: bool
    first_time: int  # activities whose first answer was right without hint 3 or 4
    on_your_own: int  # activities answered right without hint 3 or 4
    answered: int  # activities answered at all
    total: int
    medal: Medal | None  # set once the module is complete
    heading_for: Medal | None  # what the answers so far are on course for
    objectives: tuple[int, ...]  # the objectives its activities practise


def level_for(answered: int, on_your_own: int, total: int) -> Level:
    """An objective's practice level (see the module docstring)."""
    if answered == 0:
        return "not_started"
    if total > 0 and answered >= total and on_your_own >= SECURE_SHARE * total:
        return "secure"
    return "practising"


def medal_for(
    total: int, first_time: int, on_your_own: int, *, tested_out: bool = False
) -> Medal | None:
    """The medal for a finished module with `total` activities: gold if every one was right first
    time without hint 3 or 4, silver if every one was right without them, bronze if at least one
    was, else none. A module passed by testing out (`tested_out`) earns silver, or better if its
    activities earn it."""
    if total > 0 and first_time >= total:
        return "gold"
    if (total > 0 and on_your_own >= total) or tested_out:
        return "silver"
    if on_your_own > 0:
        return "bronze"
    return None


def _practice(session: Session) -> list[Activity]:
    """Every practice item a student meets on the way through the modules (see the docstring)."""
    on_segments = set(
        session.scalars(
            select(Segment.activity_id).where(
                Segment.module_id.is_not(None),
                Segment.support_for.is_(None),
                Segment.activity_id.is_not(None),
            )
        )
    )
    on_videos = set(session.scalars(select(Checkpoint.activity_id)))
    candidates = session.scalars(
        select(Activity)
        .where(Activity.module_id.is_not(None), Activity.purpose.in_(PRACTICE_PURPOSES))
        .order_by(Activity.id)
    )
    return [
        a
        for a in candidates
        if a.purpose == "retrieval" or a.id in on_segments or a.id in on_videos
    ]


@dataclass(frozen=True)
class _Answers:
    answered: set[int]
    right: set[int]
    on_own: set[int]
    first_time: set[int]


def _answers(session: Session, user_id: int, ids: Collection[int]) -> _Answers:
    """Of these activities: those answered at all, right at some point, right without hint 3 or
    4, and right without them at the first answer."""
    if not ids:
        return _Answers(set(), set(), set(), set())
    rows = session.execute(
        select(Attempt.activity_id, Attempt.correct, Attempt.hint_level)
        .where(Attempt.user_id == user_id, Attempt.activity_id.in_(ids))
        .order_by(Attempt.id)
    ).all()
    first: dict[int, bool] = {}
    for activity, correct, hint in rows:
        first.setdefault(activity, bool(correct) and hint < SUPPORT_LEVEL)
    return _Answers(
        answered=set(first),
        right={a for a, correct, _ in rows if correct},
        on_own={a for a, correct, hint in rows if correct and hint < SUPPORT_LEVEL},
        first_time={a for a, ok in first.items() if ok},
    )


def skills(session: Session, user_id: int) -> list[Skill]:
    """The student's skill profile, in objective order."""
    items = _practice(session)
    got = _answers(session, user_id, [a.id for a in items])
    out = []
    for outcome in evaluate(session, user_id):
        mine = [a.id for a in items if a.objective_id == outcome.objective.id]
        answered = sum(1 for a in mine if a in got.answered)
        own = sum(1 for a in mine if a in got.on_own)
        state = outcome.state
        out.append(
            Skill(
                objective_id=outcome.objective.id,
                text=outcome.objective.text,
                answered=answered,
                correct=sum(1 for a in mine if a in got.right),
                on_your_own=own,
                total=len(mine),
                level=level_for(answered, own, len(mine)),
                result=None if state == "not_attempted" else state,
            )
        )
    return out


def module_medals(session: Session, user_id: int) -> list[ModuleMedal]:
    """Each module's medal (or the one it is heading for), in map order. Modules with nothing
    to mark are left out."""
    items = _practice(session)
    by_id = {a.id: a for a in items}
    shown = session.execute(
        select(Segment.module_id, Segment.activity_id).where(
            Segment.module_id.is_not(None),
            Segment.support_for.is_(None),
            Segment.activity_id.is_not(None),
        )
    ).all()
    statuses: dict[int, str] = {
        row.module_id: row.status
        for row in session.execute(
            select(ModuleProgress.module_id, ModuleProgress.status).where(
                ModuleProgress.user_id == user_id,
                ModuleProgress.status.in_(("complete", "tested_out")),
            )
        )
    }
    complete = set(statuses)
    # A module passed through its quick check (FR-8.2) has a medal too (#214), and keeps it once
    # worked through (the status is then "complete"): the better of the two.
    tested_out = {m for m, status in statuses.items() if status == "tested_out"}
    tested_out |= quick_check.passed(session, user_id)
    got = _answers(session, user_id, list(by_id))
    medals = []
    for module in session.scalars(select(Module).order_by(Module.position)):
        if module.id == MASTERY_MODULE:
            continue
        mine: Sequence[int] = sorted(
            {a for m, a in shown if m == module.id and a in by_id}
            | {a.id for a in items if a.module_id == module.id and a.purpose == "retrieval"}
        )
        if not mine:
            continue
        done = [a for a in mine if a in got.answered]
        finished = module.id in complete
        # Judged on what the student was asked when they worked through it (see the docstring).
        asked = done if statuses.get(module.id) == "complete" and done else mine
        first = sum(1 for a in asked if a in got.first_time)
        own = sum(1 for a in asked if a in got.on_own)
        so_far = medal_for(
            len(done),
            sum(1 for a in done if a in got.first_time),
            sum(1 for a in done if a in got.on_own),
        )
        medal = (
            medal_for(len(asked), first, own, tested_out=module.id in tested_out)
            if finished
            else None
        )
        medals.append(
            ModuleMedal(
                module_id=module.id,
                complete=finished,
                first_time=first,
                on_your_own=own,
                answered=len(done),
                total=len(asked),
                medal=medal,
                heading_for=medal if finished else so_far if done else None,
                objectives=tuple(
                    sorted({o for a in mine if (o := by_id[a].objective_id) is not None})
                ),
            )
        )
    return medals
