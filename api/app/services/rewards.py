"""Private points and badges (SE document FR-9, issue #32).

What the rules follow (research: the ID document §7.2 and the #32 research note):

- Points are never taken away, and each thing is rewarded once: answering an activity again, or
  failing it, changes nothing.
- A badge, once earned, is never removed. Recomputing results (FR-7.6) may add badges, never take
  them; an objective badge only ever goes up a level: practised (secure in the modules' practice,
  app/services/skills.py), then bronze (met with support in the mastery check), then gold (met
  independently). It can start at any level and skip one; it never goes down.
- Badges name a skill. None counts hints, attempts, days or speed, so none can be earned by
  clicking through hints or guessing.

The activity routes award activity points through `on_attempt`. The other `on_*` functions are
for the features that own those events: objective results (#22), the review path (#23), a
completed module (app/services/modules.py, #141) and bonus quests (#31). Each adds to the session
without committing, like the rest of the services, and returns what was newly earned.
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import Exists, exists, func, select
from sqlalchemy.orm import Session

from app.models import Attempt, HintView, PointsEntry, PointsRule, User, UserBadge
from app.services.locks import lock_student

Mastery = Literal["independent", "supported", "not_yet"]
Tier = Literal["practised", "bronze", "gold"]

# An objective badge's levels, lowest first: a badge only ever moves up this list.
TIERS: tuple[Tier, ...] = ("practised", "bronze", "gold")

# The learning objectives (ID document §3.1). LO8 waits on #70; drop it here if it is cut.
OBJECTIVES: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8)

# Hint level 3 or 4 makes a correct answer "met with support" (FR-7.2).
SUPPORT_LEVEL = 3


def answer_given_away(
    session: Session,
    user_id: int,
    activity_id: int,
    before: int | None = None,
    level: int = SUPPORT_LEVEL,
) -> bool:
    """Whether this student had been shown hint `level` or higher (by default 3 or 4) on this
    activity, in any round, before their attempt with id `before` (any time, if None).
    Restarting a module (app/services/restart.py) starts its hint ladder again, but not its
    rewards: an answer once given away stays given away (13 Nov audit). A hint opened after an
    answer never counts against that answer, so hints on a restarted module's questions take
    nothing from what the first round earned (#211 review)."""
    query = select(HintView.id).where(
        HintView.user_id == user_id,
        HintView.activity_id == activity_id,
        HintView.level >= level,
    )
    if before is not None:
        query = query.where(HintView.after_attempt < before)
    return session.scalar(query.limit(1)) is not None


# --- The evidence rule ---------------------------------------------------------------------------
#
# One rule decides which answers count, for every reward (FR-9.6, review of 13 Nov on #221):
#
# 1. Only a student's first attempt at a question counts. A right answer after a wrong one is not
#    real work: it pays guessing. Restarting a module (app/services/restart.py) starts a new
#    round of it, but not a new first attempt: what a wrong first answer didn't earn, answering
#    it again after a restart doesn't earn either, so a restart can't win back what guessing lost.
# 2. An answer after hint 4, the worked answer, never counts, whatever round the hint was in:
#    the answer is the hint's, not the student's.
#
# `counts_as_evidence` applies it to one attempt and `first_tries` to many. Each reward then adds
# only its own line about hint 3: activity points are fewer after it (FR-9.2), and module points,
# First Module and bonus quests need an answer without hint 3 or 4 (`real_work`).

# Hint 4 is the worked answer (FR-4.4): an answer after it is never the student's own.
WORKED_LEVEL = 4


def first_tries(session: Session, user_id: int, activity_ids: Collection[int]) -> set[int]:
    """The ids of this student's first attempts at these activities, right or wrong, one per
    activity at most (rule 1 above)."""
    if not activity_ids:
        return set()
    firsts = session.scalars(
        select(func.min(Attempt.id))
        .where(Attempt.user_id == user_id, Attempt.activity_id.in_(activity_ids))
        .group_by(Attempt.activity_id)
    )
    return set(firsts)


def counts_as_evidence(session: Session, attempt: Attempt) -> bool:
    """Whether this attempt counts for any reward: right, the student's first at the activity, and
    not after the worked answer (the evidence rule above). `attempt` must be flushed, so it has its id."""
    return (
        attempt.correct
        and attempt.hint_level < WORKED_LEVEL
        and attempt.id in first_tries(session, attempt.user_id, [attempt.activity_id])
        and not answer_given_away(
            session, attempt.user_id, attempt.activity_id, before=attempt.id, level=WORKED_LEVEL
        )
    )


def supported(session: Session, attempt: Attempt) -> bool:
    """Whether hint 3 or 4 had been shown before this attempt, in its round or an earlier one."""
    return attempt.hint_level >= SUPPORT_LEVEL or answer_given_away(
        session, attempt.user_id, attempt.activity_id, before=attempt.id
    )


def real_work(session: Session, attempt: Attempt) -> bool:
    """Evidence (`counts_as_evidence`) given without hint 3 or 4: what module points, First
    Module and a bonus quest need."""
    return counts_as_evidence(session, attempt) and not supported(session, attempt)


def _hint_before(level: int) -> Exists:
    """SQL: the student had been shown hint `level` or higher on the attempt's activity before
    the attempt, in any round (the same test as `answer_given_away`, as a column)."""
    return exists().where(
        HintView.user_id == Attempt.user_id,
        HintView.activity_id == Attempt.activity_id,
        HintView.level >= level,
        HintView.after_attempt < Attempt.id,
    )


@dataclass(frozen=True)
class FirstAnswers:
    """What a student's first attempts at some activities count for (the evidence rule)."""

    # Real work (`real_work`): the first attempt was right, before hint 3 or 4 in any round.
    on_own: set[int]
    # Real work given before any hint at all.
    first_time: set[int]


def first_answers(session: Session, user_id: int, activity_ids: Collection[int]) -> FirstAnswers:
    """The evidence rule over many activities in one query: the same answer as `real_work` on
    each first attempt, without a query per activity (#221 re-review: the skill profile ran 369
    queries). Not after hint 3 or 4 implies not after the worked answer, so rule 2 holds too."""
    if not activity_ids:
        return FirstAnswers(set(), set())
    firsts = (
        select(func.min(Attempt.id))
        .where(Attempt.user_id == user_id, Attempt.activity_id.in_(activity_ids))
        .group_by(Attempt.activity_id)
    )
    rows = session.execute(
        select(
            Attempt.activity_id,
            (Attempt.hint_level == 0) & ~_hint_before(1),
        ).where(
            Attempt.id.in_(firsts),
            Attempt.correct.is_(True),
            Attempt.hint_level < SUPPORT_LEVEL,
            ~_hint_before(SUPPORT_LEVEL),
        )
    ).all()
    return FirstAnswers(
        on_own={activity for activity, _ in rows},
        first_time={activity for activity, unhinted in rows if unhinted},
    )


def real_work_on(session: Session, user_id: int, activity_ids: Collection[int]) -> set[int]:
    """The activities among these on which this student has done real work (`real_work`), in
    one query (`first_answers`)."""
    return first_answers(session, user_id, activity_ids).on_own


# Used when a rule's row is missing, so a deleted row never breaks submitting an answer.
DEFAULT_POINTS = {
    "activity_correct": 10,
    "activity_correct_supported": 4,
    "module_completed": 25,
    "objective_independent": 30,
    "objective_supported": 15,
    "bonus_quest": 20,
}

# Every badge id the server awards. Names and pictures: web/src/components/achievements.ts.
OBJECTIVE_BADGES = {n: f"lo{n}" for n in OBJECTIVES}
READY_FOR_LECTURE = "ready-for-lecture"
CAME_BACK_STRONGER = "came-back-stronger"
SOLO_RUN = "solo-run"
QUEST = "quest"
ALL_QUESTS = "all-quests"
FIRST_MODULE = "first-module"
BADGES = frozenset(
    {
        *OBJECTIVE_BADGES.values(),
        READY_FOR_LECTURE,
        CAME_BACK_STRONGER,
        SOLO_RUN,
        QUEST,
        ALL_QUESTS,
        FIRST_MODULE,
    }
)


@dataclass(frozen=True)
class Earned:
    """What one event earned: points, and badges that are new or went up a tier."""

    points: int = 0
    badges: tuple[UserBadge, ...] = ()

    def __add__(self, other: "Earned") -> "Earned":
        return Earned(self.points + other.points, self.badges + other.badges)


def points_for(session: Session, event: str) -> int:
    rule = session.get(PointsRule, event)
    return rule.points if rule is not None else DEFAULT_POINTS[event]


def _add_points(
    session: Session, user_id: int, event: str, ref: str, points: int | None = None
) -> Earned:
    """Give `points` (by default the rule's) for `ref`, unless this student already has them."""
    exists = session.scalar(
        select(PointsEntry.id).where(PointsEntry.user_id == user_id, PointsEntry.ref == ref)
    )
    if exists is not None:
        return Earned()
    amount = points_for(session, event) if points is None else points
    session.add(PointsEntry(user_id=user_id, event=event, ref=ref, points=amount))
    session.flush()
    return Earned(points=amount)


def _award(
    session: Session, user_id: int, badge: str, ref: str = "", tier: Tier | None = None
) -> Earned:
    """Give a badge, or raise an objective badge to a higher level (practised, bronze, gold).
    Never lowers or removes one."""
    if badge not in BADGES:
        raise ValueError(f"No badge {badge!r} in the catalogue.")
    held = session.scalar(
        select(UserBadge).where(
            UserBadge.user_id == user_id, UserBadge.badge == badge, UserBadge.ref == ref
        )
    )
    if held is None:
        held = UserBadge(user_id=user_id, badge=badge, ref=ref, tier=tier)
        session.add(held)
    elif tier is not None and held.tier in TIERS and TIERS.index(tier) > TIERS.index(held.tier):
        held.tier = tier
        held.upgraded_at = datetime.now(UTC)
        held.seen_at = None  # announce the upgrade
    else:
        return Earned()
    session.flush()
    return Earned(badges=(held,))


def on_attempt(session: Session, attempt: Attempt) -> Earned:
    """Points for an activity answered right at the **first** attempt (FR-9.1): the full points,
    or fewer if it came after hint 3 (FR-9.2). It follows the evidence rule above: a right answer
    after a wrong one, in any round, earns nothing (paying it paid guessing,
    and wrong-then-right on every item earned more than right first time: review of 13 Nov,
    High 7), and neither does one after hint 4, the worked answer. A correct answer to an
    activity already rewarded earns nothing either. `attempt` must be flushed, so it has its
    id."""
    if not counts_as_evidence(session, attempt):
        return Earned()
    event = "activity_correct_supported" if supported(session, attempt) else "activity_correct"
    return _add_points(session, attempt.user_id, event, f"activity:{attempt.activity_id}")


def on_practised(session: Session, user_id: int, objective: int) -> Earned:
    """An objective is secure in practice (app/services/skills.py `level_for`): its badge at the
    first level, Practised, unless the student already holds it at any level. Earns no points:
    the practice answers already earned theirs (FR-9.1), and the mastery check's bronze or gold
    gives the objective's points in full when it comes, so nothing is lost on the way up."""
    if objective not in OBJECTIVES:
        raise ValueError(f"No learning objective {objective}.")
    return _award(session, user_id, OBJECTIVE_BADGES[objective], tier="practised")


def on_module_completed(session: Session, user_id: int, module_id: int) -> Earned:
    """A module completed (FR-9.1): its points once, and the First Module badge with the first
    (FR-9.3). Completing it again, after rereading, earns nothing more."""
    return _add_points(session, user_id, "module_completed", f"module:{module_id}") + _award(
        session, user_id, FIRST_MODULE
    )


def on_objective_result(
    session: Session,
    user_id: int,
    objective: int,
    result: Mastery,
    results: Mapping[int, Mastery],
    *,
    via_review: bool = False,
    objectives: Collection[int] = OBJECTIVES,
) -> Earned:
    """Call when an objective's result changes (app/services/mastery.py). `results` is the
    student's result on every objective they have one for; `via_review` is true when the review
    path (#23) got them there. `objectives` is the course's objectives, the ones Ready for the
    Lecture and Solo Run need: the mastery service passes those in the database.

    "Not yet" earns nothing and takes nothing away. Met with support earns the objective's bronze
    badge and its points; met independently earns gold and the full points, topping up what an
    earlier "with support" gave, so the total is the same either way round.
    """
    if objective not in OBJECTIVES:
        raise ValueError(f"No learning objective {objective}.")
    if result == "not_yet":
        return Earned()
    results = {**results, objective: result}
    ref = f"objective:{objective}"
    earned = Earned()

    if result == "supported":
        earned += _add_points(session, user_id, "objective_supported", ref)
        earned += _award(session, user_id, OBJECTIVE_BADGES[objective], tier="bronze")
    else:
        full = points_for(session, "objective_independent")
        earlier = session.scalar(
            select(PointsEntry.points).where(PointsEntry.user_id == user_id, PointsEntry.ref == ref)
        )
        if earlier is None:
            earned += _add_points(session, user_id, "objective_independent", ref, full)
        elif earlier < full:
            top_up = full - earlier
            earned += _add_points(
                session, user_id, "objective_independent", f"{ref}:independent", top_up
            )
        earned += _award(session, user_id, OBJECTIVE_BADGES[objective], tier="gold")

    if via_review:
        earned += _award(session, user_id, CAME_BACK_STRONGER)
    if all(results.get(n) in ("independent", "supported") for n in objectives):
        earned += _award(session, user_id, READY_FOR_LECTURE)
    if all(results.get(n) == "independent" for n in objectives):
        earned += _award(session, user_id, SOLO_RUN)
    return earned


def on_bonus_quest(
    session: Session, user_id: int, quest_id: int, *, all_quests_done: bool
) -> Earned:
    """A bonus quest finished (#31, #87): its points and its own badge, and All Quests with the
    last. `quest_id` is the quest's activity id, so a badge keeps naming the same quest."""
    earned = _add_points(session, user_id, "bonus_quest", f"quest:{quest_id}")
    earned += _award(session, user_id, QUEST, ref=str(quest_id))
    if all_quests_done:
        earned += _award(session, user_id, ALL_QUESTS)
    return earned


def total_points(session: Session, user_id: int) -> int:
    total = session.scalar(
        select(func.coalesce(func.sum(PointsEntry.points), 0)).where(PointsEntry.user_id == user_id)
    )
    return int(total or 0)


def activity_refs(activity_id: int) -> tuple[str, ...]:
    """The points refs an answer to this activity can earn: its own, or a bonus quest's."""
    return (f"activity:{activity_id}", f"quest:{activity_id}")


def points_for_refs(session: Session, user_id: int, refs: Collection[str]) -> int:
    """This student's points for these refs, so a route can tell what one answer earned."""
    total = session.scalar(
        select(func.coalesce(func.sum(PointsEntry.points), 0)).where(
            PointsEntry.user_id == user_id, PointsEntry.ref.in_(refs)
        )
    )
    return int(total or 0)


def badges_of(session: Session, user_id: int) -> list[UserBadge]:
    return list(
        session.scalars(
            select(UserBadge).where(UserBadge.user_id == user_id).order_by(UserBadge.id)
        )
    )


def mark_seen(session: Session, user_id: int) -> None:
    """The student has been shown every badge they have (not committed). Takes the student's write
    lock (app/services/locks.py), so a badge an answer is awarding at the same moment is either
    marked seen with the rest or announced next time, never half of each."""
    lock_student(session, user_id)
    now = datetime.now(UTC)
    for badge in badges_of(session, user_id):
        if badge.seen_at is None:
            badge.seen_at = now
    session.flush()


def set_hide_rewards(session: Session, user: User, hide: bool) -> None:
    """Hide or show points and badges (FR-9.5). Badges are still earned while hidden. Either way
    everything so far is marked seen, so turning them back on shows them on the shelf without a
    burst of announcements."""
    user.hide_rewards = hide
    mark_seen(session, user.id)
