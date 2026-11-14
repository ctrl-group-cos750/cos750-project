"""The skill profile and module medals (SE document FR-9.7, FR-9.8; issue #214).

Both are read from attempts on each request, like the mastery report, and store nothing.

**Skill profile.** One entry per learning objective. Before the mastery check has a result it
shows practice progress as one of three coarse levels, not a percentage of a handful of answers:

- **not started**: none of the objective's practice items answered yet,
- **practising**: some answered,
- **secure**: every one answered, and at least 80% of them right on your own (the same line as
  the ID document's typical criterion, "at least 4 of 5").

**On your own** follows the evidence rule every reward shares (FR-9.6, `rewards.counts_as_evidence`):
only a student's first attempt at a question counts, so a right answer after a wrong one is not
real work; and an answer after the worked answer never counts. The skill profile and medals go one
step further, as module points do: the first attempt must also come before hint 3 or 4, in any
round. Worked out here in one query (`_answers`), because the profile also needs it per round
(below); for medals it gives exactly `rewards.first_answers`, the query module points use, and a
test holds the two together.

**Where the student stands now.** The skill profile's level and the Practised badge count, for
each practice item, the first answer in the latest round of its module in which the student
answered it (`_answers(..., latest_round=True)`): restarting a module (FR-2.8) gives its items a
new first answer, so practice after a slip can make an objective secure again, while an item not
redone yet keeps the result it had (#222 review by Koos: the profile shows where the student stands
now, ID document §7.2 and ARCS confidence, and practice is where mistakes are expected). Hint 3 or
4 seen in an earlier round still counts against a later answer, as everywhere (FR-2.8). Points and
medals keep the first attempt ever, so a restart can't win back what guessing lost there (FR-9.6).

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

- *on your own* if the student's first answer to it was right, before hint 3 or 4 (above),
- *first time* if it was also given before any hint at all.

Under the evidence rule a retry never counts, so "first time" can no longer mean "not after a
wrong answer" (that is now every activity on your own); it means without a hint.

Then (`medal_for`, the one place the rule lives):

- **gold**: every activity right first time, without a hint,
- **silver**: every activity right on your own,
- **finished**: the module finished with at least one activity right on your own,
- **none**: the module finished without one (every answer wrong, moved on after two tries): the
  same line as the module's points and First Module badge (app/services/modules.py
  `reward_module`), so walking through a module earns nothing (#215 review).

A module the student worked through to the end is judged on the activities they answered on the
way. An activity added to it afterwards isn't one they were asked, so it can't lower the medal they
finished with (review of #223, Must fix 2: module 1's warm-up question left the medal set and a
graph-words item joined it, and every finished student's gold became bronze). Working through a
module answers every activity it asks for, so for anyone who finished it since, that is all of
them. An activity first answered after the module was finished doesn't join it either: going back
to an item that joined later is more work, and more work never lowers a medal (review of #223, new
finding 2: one wrong answer to the new item 194 turned a kept gold into bronze).

**Where to improve it** (#214). Each objective says where the student can work on it, worked
out here from the content so the web doesn't guess (`improve`):

- *not started* or *practising*: **practise** in the first module, in course order, with a practice
  item on it the student hasn't answered yet, at that item's segment when the student has already
  reached it (a segment further on can't be opened yet, FR-2.7, so the module opens where it
  resumes);
- *practising*, but secure is out of reach this round: once more than a fifth of an objective's
  practice items had a first answer (this round) that wasn't on your own, answering the rest can't
  make it secure (an objective with fewer than five allows none). Sending the student on to
  practise would send them somewhere that can't help (#222 re-review, N1). A **restart** of the
  module with the first such item can (above), so it points there once that module is finished
  and can be restarted; until then it points to the mastery **check** (module 6), where the
  objective is still met in full;
- *secure*, or bronze (met with support, which only a review path gives): **revisit** the first module that practises it
  (the result stands; going over it again is the student's choice);
- *not yet* from the mastery check: its **review** path, the designed route after module 6, once
  open (FR-7.5);
- gold: nothing.

Never into module 6 to practise: its items aren't practice. The check kind only says that the
mastery check is where the objective is decided now.

A module whose quick check the student passed earns silver: the check showed the student can do
it on their own, but not every activity was answered. That stays when the student works through
the module afterwards: more work never lowers a medal, so they get the better of the two
(`quick_check.passed` is read from the check's answers, not from the module's status, which
becomes "complete"). A module with nothing to mark (module 0's
diagnostic, module 6's mastery check, whose results are the report) has no medal. While a module
is in progress, `heading_for` is the medal the answers so far are on course for, counting only
activities already answered.
"""

from bisect import bisect_left
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy import Exists, exists, select
from sqlalchemy.orm import Session

from app.models import (
    Activity,
    Attempt,
    Checkpoint,
    Event,
    HintView,
    Module,
    ModuleProgress,
    Segment,
    Video,
)
from app.services import quick_check, rewards
from app.services.mastery import MASTERY_MODULE, State, evaluate
from app.services.modules import module_locked
from app.services.rewards import SUPPORT_LEVEL

# "finished", not "bronze": bronze is an objective badge's level (met with support), so the
# module medal for finishing has its own name (#214).
Medal = Literal["gold", "silver", "finished"]

# The purposes that count as practice for the skill profile and for a module's medal.
PRACTICE_PURPOSES: frozenset[str] = frozenset({"practice", "retrieval"})


Level = Literal["not_started", "practising", "secure"]

# Share of an objective's practice items right without hint 3 or 4 that makes it secure.
SECURE_SHARE = 0.8


ImproveKind = Literal["practise", "revisit", "review", "check", "restart"]


@dataclass(frozen=True)
class Improve:
    """Where the student can work on an objective (see the docstring)."""

    kind: ImproveKind
    module_id: int | None = None  # the module (its id is its number): practise, revisit, check
    segment: int | None = None  # the segment to open at, 0-based, when the student can open it
    objective_id: int | None = None  # the review path's objective, for review
    # The module isn't open to this student yet: the mastery check, before modules 1 to 5 are done.
    # The profile then says where it will be shown instead of linking to a locked page.
    locked: bool = False


@dataclass(frozen=True)
class Skill:
    objective_id: int
    text: str
    answered: int  # practice items answered at all
    correct: int  # answered right at some point
    on_your_own: int  # answered right on your own: the first attempt, before hint 3 or 4
    total: int
    level: Level
    result: State | None  # None until the mastery check (or a review path) decides it
    improve: Improve | None = None
    # The modules, in course order, holding every item counted toward it (practice questions and
    # spaced retrieval questions): where its badge's first level, Practised, is earned, so doing
    # what the list says is enough to get there (#222 review, A3).
    modules: tuple[int, ...] = ()


@dataclass(frozen=True)
class ModuleMedal:
    module_id: int
    complete: bool
    first_time: int  # activities whose first answer was right before any hint
    on_your_own: int  # activities whose first answer was right before hint 3 or 4
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
    """The medal for a finished module with `total` activities: gold if every one was right at the
    first attempt before any hint, silver if every one was right at the first attempt before hint 3
    or 4, finished if at least one was, else none. A module passed by testing out (`tested_out`)
    earns silver, or better if its activities earn it."""
    if total > 0 and first_time >= total:
        return "gold"
    if (total > 0 and on_your_own >= total) or tested_out:
        return "silver"
    if on_your_own > 0:
        return "finished"
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
    first_at: dict[int, datetime]  # when each was first answered


def _utc(moment: datetime) -> datetime:
    """`moment` as an aware time: SQLite gives back naive UTC times, Postgres aware ones."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def _hint_before(level: int) -> Exists:
    """SQL: this student had been shown hint `level` or higher on the attempt's activity before
    the attempt, in any round (a hint opened after an answer never counts against it)."""
    return exists().where(
        HintView.user_id == Attempt.user_id,
        HintView.activity_id == Attempt.activity_id,
        HintView.level >= level,
        HintView.after_attempt < Attempt.id,
    )


def _round_starts(session: Session, user_id: int) -> dict[int, list[int]]:
    """Each module's restart boundaries for this student, in order: attempts at its activities with
    an id above a boundary, and not above the next, are that round's (app/services/restart.py)."""
    starts: dict[int, set[int]] = {}
    for ref, payload in session.execute(
        select(Event.ref, Event.payload).where(
            Event.user_id == user_id, Event.type == "module_restarted"
        )
    ):
        after = (payload or {}).get("after_attempt")
        if ref.startswith("module:") and isinstance(after, int):
            starts.setdefault(int(ref.removeprefix("module:")), set()).add(after)
    # The latest restart is on its progress row too, in case its event is missing.
    for module_id, after in session.execute(
        select(ModuleProgress.module_id, ModuleProgress.restarted_after_attempt).where(
            ModuleProgress.user_id == user_id,
            ModuleProgress.restarted_after_attempt.is_not(None),
        )
    ):
        if after is not None:
            starts.setdefault(module_id, set()).add(after)
    return {module_id: sorted(afters) for module_id, afters in starts.items()}


def _answers(
    session: Session, user_id: int, items: Sequence[Activity], *, latest_round: bool = False
) -> _Answers:
    """Of these activities: those answered at all, right at some point, right on your own (the
    first attempt, right, before hint 3 or 4: the module docstring), and right first time (that,
    before any hint). The first attempt is the first ever, for medals; with `latest_round`, the
    first in the latest round of its module in which the student answered it, for the skill
    profile and Practised (see "Where the student stands now")."""
    ids = [a.id for a in items]
    if not ids:
        return _Answers(set(), set(), set(), set(), {})
    rows = session.execute(
        select(
            Attempt.id,
            Attempt.activity_id,
            Attempt.correct,
            Attempt.created_at,
            (Attempt.hint_level < SUPPORT_LEVEL) & ~_hint_before(SUPPORT_LEVEL),
            (Attempt.hint_level == 0) & ~_hint_before(1),
        )
        .where(Attempt.user_id == user_id, Attempt.activity_id.in_(ids))
        .order_by(Attempt.id)
    ).all()
    starts = _round_starts(session, user_id) if latest_round else {}
    module = {a.id: a.module_id for a in items}

    def round_of(activity: int, attempt: int) -> int:
        return bisect_left(starts.get(module[activity] or 0, []), attempt)

    # The evidence rule (FR-9.6): only the first attempt at each activity is evidence, so wrong
    # then right (guessing until right) is never on your own (#222 review, A1). Per round, with
    # `latest_round`: a later round's first attempt replaces an earlier round's.
    first: dict[int, tuple[int, bool, bool]] = {}
    # When each activity was first answered, in any round: a finished module's medal is judged on
    # the activities answered before it was finished (`module_medals`; review of #223).
    first_at: dict[int, datetime] = {}
    for attempt, activity, correct, created, unsupported, unhinted in rows:
        first_at.setdefault(activity, _utc(created))
        at = round_of(activity, attempt)
        if activity not in first or at > first[activity][0]:
            ok = bool(correct) and bool(unsupported)
            first[activity] = (at, ok, ok and bool(unhinted))
    return _Answers(
        answered=set(first),
        right={a for _, a, correct, _, _, _ in rows if correct},
        on_own={a for a, (_, own, _) in first.items() if own},
        first_time={a for a, (_, _, unhinted) in first.items() if unhinted},
        first_at=first_at,
    )


def _places(session: Session, items: Sequence[Activity]) -> dict[int, tuple[int, int, int | None]]:
    """Where each practice item is met: (module position, module id, segment index or None). The
    index counts every segment of the module in order, as the module page does; a module's
    retrieval question comes before its segments (None); a video checkpoint's question is at the
    video's segment."""
    modules = {m.id: m.position for m in session.scalars(select(Module))}
    index: dict[int, int] = {}  # activity id -> segment index
    at_segment: dict[int, tuple[int, int]] = {}  # segment id -> (module id, segment index)
    rows = session.execute(
        select(Segment.id, Segment.module_id, Segment.activity_id, Segment.support_for)
        .where(Segment.module_id.is_not(None))
        .order_by(Segment.module_id, Segment.position)
    ).all()
    counter: dict[int, int] = {}
    for segment_id, module_id, activity_id, support_for in rows:
        module_id = cast(int, module_id)  # not None, by the query
        i = counter.get(module_id, 0)
        counter[module_id] = i + 1
        at_segment[segment_id] = (module_id, i)
        if activity_id is not None and support_for is None:
            index.setdefault(activity_id, i)
    # A checkpoint's question is met at its video's segment.
    videos = {
        activity_id: at_segment[segment_id]
        for activity_id, segment_id in session.execute(
            select(Checkpoint.activity_id, Video.segment_id).join(
                Video, Video.id == Checkpoint.video_id
            )
        ).all()
        if segment_id in at_segment
    }
    places: dict[int, tuple[int, int, int | None]] = {}
    for a in items:
        module_id = cast(int, a.module_id)  # practice items all have a module
        if a.purpose == "retrieval":
            places[a.id] = (modules.get(module_id, 0), module_id, None)
        elif a.id in index:
            places[a.id] = (modules.get(module_id, 0), module_id, index[a.id])
        elif a.id in videos:
            at_module, at = videos[a.id]
            places[a.id] = (modules.get(at_module, 0), at_module, at)
    return places


def _improve(
    level: Level,
    result: State | None,
    review_open: bool,
    objective_id: int,
    mine: Sequence[int],
    places: dict[int, tuple[int, int, int | None]],
    got: _Answers,
    reached: dict[int, int | None],
    check_locked: bool = False,
) -> Improve | None:
    """Where to work on one objective (see the docstring). `reached` is each module's furthest
    segment for this student, or None where every segment can be opened (worked through)."""
    if result == "met_independently":
        return None
    if result == "not_yet":
        return Improve("review", objective_id=objective_id) if review_open else None
    ordered = sorted(
        (a for a in mine if a in places and places[a][1] != MASTERY_MODULE),
        key=lambda a: (places[a][0], -1 if places[a][2] is None else places[a][2], a),
    )
    if not ordered:
        return None
    if result == "met_with_support" or level == "secure":
        return Improve("revisit", module_id=places[ordered[0]][1])
    # A first answer that wasn't on your own counts until the module is restarted (FR-9.6): with
    # too many of those, answering the rest can't make it secure this round.
    missed = sum(1 for a in mine if a in got.answered and a not in got.on_own)
    if len(mine) - missed < SECURE_SHARE * len(mine):
        # A restart gives the module's items a new first answer (the module docstring), so restart
        # the first module with such an item, once it is finished (only then can it be restarted,
        # FR-2.8; `reached` is None for it). Until then, the mastery check decides it.
        restartable = [
            places[a][1]
            for a in ordered
            if a in got.answered and a not in got.on_own and reached.get(places[a][1], 0) is None
        ]
        if restartable:
            return Improve("restart", module_id=restartable[0])
        return Improve("check", module_id=MASTERY_MODULE, locked=check_locked)
    todo = [a for a in ordered if a not in got.answered]
    _, module_id, segment = places[(todo or ordered)[0]]
    furthest = reached.get(module_id, 0)
    if segment is not None and furthest is not None and segment > furthest:
        segment = None  # not reached yet: the module opens where it resumes
    return Improve("practise", module_id=module_id, segment=segment)


def _reached(session: Session, user_id: int) -> dict[int, int | None]:
    """Each module's furthest segment for this student; None for one worked through, where any
    segment can be opened. A module never started has reached its first (0, the default)."""
    return {
        row.module_id: None if row.status == "complete" else row.current_segment_position
        for row in session.scalars(select(ModuleProgress).where(ModuleProgress.user_id == user_id))
    }


def skills(session: Session, user_id: int) -> list[Skill]:
    """The student's skill profile, in objective order."""
    items = _practice(session)
    got = _answers(session, user_id, items, latest_round=True)
    places = _places(session, items)
    reached = _reached(session, user_id)
    check_locked = module_locked(session, user_id, MASTERY_MODULE)
    out = []
    for outcome in evaluate(session, user_id):
        mine = [a.id for a in items if a.objective_id == outcome.objective.id]
        practised_in = sorted(
            {
                (places[a.id][0], places[a.id][1])
                for a in items
                if a.objective_id == outcome.objective.id
                and a.id in places
                and places[a.id][1] != MASTERY_MODULE
            }
        )
        answered = sum(1 for a in mine if a in got.answered)
        own = sum(1 for a in mine if a in got.on_own)
        state = outcome.state
        level = level_for(answered, own, len(mine))
        result = None if state == "not_attempted" else state
        out.append(
            Skill(
                objective_id=outcome.objective.id,
                text=outcome.objective.text,
                answered=answered,
                correct=sum(1 for a in mine if a in got.right),
                on_your_own=own,
                total=len(mine),
                level=level,
                result=result,
                improve=_improve(
                    level,
                    result,
                    outcome.review is not None,
                    outcome.objective.id,
                    mine,
                    places,
                    got,
                    reached,
                    check_locked,
                ),
                modules=tuple(module_id for _, module_id in practised_in),
            )
        )
    return out


def secure_objectives(
    session: Session, user_id: int, only: Collection[int] | None = None
) -> set[int]:
    """The objectives this student is secure in, in practice (`level_for`), of `only` if given,
    for the Practised badge: the skill profile's count, without the rest of it. "On your own" is
    real work (`_answers`), so an answer given away by hint 3 or 4 before a module's restart
    doesn't count after it, and only a first attempt counts (the evidence rule, FR-9.6; #222
    review, A1): the first in the latest round, as on the profile, so practice after a restart
    can earn it (#222 review by Koos)."""
    items = [a for a in _practice(session) if a.objective_id is not None]
    if only is not None:
        items = [a for a in items if a.objective_id in only]
    got = _answers(session, user_id, items, latest_round=True)
    answered_ids, own_ids = got.answered, got.on_own
    secure = set()
    for objective in {cast(int, a.objective_id) for a in items}:
        mine = [a.id for a in items if a.objective_id == objective]
        answered = sum(1 for a in mine if a in answered_ids)
        own = sum(1 for a in mine if a in own_ids)
        if level_for(answered, own, len(mine)) == "secure":
            secure.add(objective)
    return secure


def award_practised(
    session: Session, user_id: int, only: Collection[int] | None = None
) -> rewards.Earned:
    """Give the Practised badge for every objective this student is now secure in (of `only` if
    given). A badge already held, at any level, stays as it is (rewards.on_practised). Called after
    each practice answer (app/services/attempts.py) and by the seed for students who were secure
    before badges had levels (`backfill_practised`). Not committed."""
    earned = rewards.Earned()
    for objective in sorted(secure_objectives(session, user_id, only)):
        if objective in rewards.OBJECTIVES:
            earned += rewards.on_practised(session, user_id, objective)
    return earned


def backfill_practised(session: Session) -> int:
    """Practised badges for students already secure before badges had levels (#214). Safe to run
    on every seed: a badge is given once and never lowered. Not committed. Returns how many
    badges were given."""
    given = 0
    for user_id in sorted(set(session.scalars(select(Attempt.user_id).distinct()))):
        given += len(award_practised(session, user_id).badges)
    return given


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
    statuses: dict[int, str] = {}
    completed_at: dict[int, datetime] = {}
    for row in session.execute(
        select(ModuleProgress.module_id, ModuleProgress.status, ModuleProgress.completed_at).where(
            ModuleProgress.user_id == user_id,
            ModuleProgress.status.in_(("complete", "tested_out")),
        )
    ):
        statuses[row.module_id] = row.status
        if row.completed_at is not None:
            completed_at[row.module_id] = _utc(row.completed_at)
    complete = set(statuses)
    # A module passed through its quick check (FR-8.2) has a medal too (#214), and keeps it once
    # worked through (the status is then "complete"): the better of the two.
    tested_out = {m for m, status in statuses.items() if status == "tested_out"}
    tested_out |= quick_check.passed(session, user_id)
    got = _answers(session, user_id, items)
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
        asked = mine
        if statuses.get(module.id) == "complete" and done:
            asked = done
            if (end := completed_at.get(module.id)) is not None:
                asked = [a for a in done if got.first_at[a] <= end] or done
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
                # Over the same activities as `total`, so it is never more: a finished module is
                # judged on those it asked (review of #223, nit 4).
                answered=sum(1 for a in asked if a in got.answered),
                total=len(asked),
                medal=medal,
                heading_for=medal if finished else so_far if done else None,
                objectives=tuple(
                    sorted({o for a in mine if (o := by_id[a].objective_id) is not None})
                ),
            )
        )
    return medals
