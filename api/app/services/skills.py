"""The skill profile and module medals (SE document FR-9.7, FR-9.8; issue #214).

Both are read from attempts on each request, like the mastery report, and store nothing.

**Skill profile.** One entry per learning objective. Before the mastery check has a result it
shows practice progress: how many of the objective's practice items the student has answered
correctly, of how many there are. Practice items are the module activities tagged with the
objective whose purpose is practice or retrieval, that every student meets on the way through a
module: on a module segment that is not extra support (FR-8.4), a module's own retrieval
question, or a video checkpoint's question. Bonus quests (optional), skip checks, support-only
items, review-path items and mastery items are left out, so the total is one every student can
reach and the bar never measures the check. Once the mastery check (or a review path) has given
the objective a result, `result` carries it, and the profile shows gold, bronze or not yet from it.

**Module medals.** A finished module earns a medal for how much of it the student did on their
own. Each activity the module asks every student to answer (as above, without the diagnostic,
which finds gaps rather than marking) counts as *on your own* once it has been answered correctly
without hint 3 or 4 (the same line FR-7.2 and FR-9.2 draw):

- **gold**: every activity on your own,
- **silver**: at least half of them on your own,
- **bronze**: the module finished.

Like the badges (app/services/rewards.py), a medal never counts attempts, time or speed: an
activity answered right on the third try without hint 3 or 4 is as good as one right first time.
A module with nothing to mark (module 0's diagnostic, module 6's mastery check, whose results are
the report) has no medal. While a module is in progress, `heading_for` is the medal the answers
so far are on course for, counting only activities already answered.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Checkpoint, Module, ModuleProgress, Segment
from app.services.mastery import MASTERY_MODULE, State, evaluate
from app.services.rewards import SUPPORT_LEVEL

Medal = Literal["gold", "silver", "bronze"]

# The purposes that count as practice for the skill profile and for a module's medal.
PRACTICE_PURPOSES: frozenset[str] = frozenset({"practice", "retrieval"})


@dataclass(frozen=True)
class Skill:
    objective_id: int
    text: str
    correct: int
    total: int
    result: State | None  # None until the mastery check (or a review path) decides it


@dataclass(frozen=True)
class ModuleMedal:
    module_id: int
    complete: bool
    on_your_own: int  # activities answered right without hint 3 or 4
    answered: int  # activities answered at all
    total: int
    medal: Medal | None  # set once the module is complete
    heading_for: Medal | None  # what the answers so far are on course for
    objectives: tuple[int, ...]  # the objectives its activities practise


def medal_for(on_your_own: int, total: int) -> Medal:
    """The medal for a finished module with `total` activities, `on_your_own` of them answered
    right without hint 3 or 4. Gold for all, silver for at least half, else bronze."""
    if on_your_own >= total:
        return "gold"
    if on_your_own * 2 >= total:
        return "silver"
    return "bronze"


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


def _results(session: Session, user_id: int, ids: Collection[int]) -> tuple[set[int], set[int]]:
    """Of these activities: those answered at all, and those answered right without hint 3 or 4.
    Also returns nothing for an empty list without asking the database."""
    if not ids:
        return set(), set()
    rows = session.execute(
        select(Attempt.activity_id, Attempt.correct, Attempt.hint_level).where(
            Attempt.user_id == user_id, Attempt.activity_id.in_(ids)
        )
    ).all()
    answered = {a for a, _, _ in rows}
    on_own = {a for a, correct, hint in rows if correct and hint < SUPPORT_LEVEL}
    return answered, on_own


def skills(session: Session, user_id: int) -> list[Skill]:
    """The student's skill profile, in objective order."""
    items = _practice(session)
    ids = [a.id for a in items]
    right = (
        set(
            session.scalars(
                select(Attempt.activity_id).where(
                    Attempt.user_id == user_id,
                    Attempt.activity_id.in_(ids),
                    Attempt.correct.is_(True),
                )
            )
        )
        if ids
        else set()
    )
    out = []
    for outcome in evaluate(session, user_id):
        mine = [a.id for a in items if a.objective_id == outcome.objective.id]
        state = outcome.state
        out.append(
            Skill(
                objective_id=outcome.objective.id,
                text=outcome.objective.text,
                correct=sum(1 for a in mine if a in right),
                total=len(mine),
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
    complete = set(
        session.scalars(
            select(ModuleProgress.module_id).where(
                ModuleProgress.user_id == user_id, ModuleProgress.status == "complete"
            )
        )
    )
    answered, on_own = _results(session, user_id, list(by_id))
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
        own = sum(1 for a in mine if a in on_own)
        done = [a for a in mine if a in answered]
        own_done = sum(1 for a in done if a in on_own)
        finished = module.id in complete
        medals.append(
            ModuleMedal(
                module_id=module.id,
                complete=finished,
                on_your_own=own,
                answered=len(done),
                total=len(mine),
                medal=medal_for(own, len(mine)) if finished else None,
                heading_for=(
                    medal_for(own, len(mine))
                    if finished
                    else medal_for(own_done, len(done))
                    if done
                    else None
                ),
                objectives=tuple(
                    sorted({o for a in mine if (o := by_id[a].objective_id) is not None})
                ),
            )
        )
    return medals
