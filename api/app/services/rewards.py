"""Private points and badges (SE document FR-9, issue #32).

What the rules follow (research: the ID document §7.2 and the #32 research note):

- Points are never taken away, and each thing is rewarded once: answering an activity again, or
  failing it, changes nothing.
- A badge, once earned, is never removed. Recomputing results (FR-7.6) may add badges, never take
  them; an objective badge only ever goes up, from bronze (met with support) to gold (met
  independently).
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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Attempt, PointsEntry, PointsRule, User, UserBadge
from app.services.locks import lock_student

Mastery = Literal["independent", "supported", "not_yet"]
Tier = Literal["bronze", "gold"]

# The learning objectives (ID document §3.1). LO8 waits on #70; drop it here if it is cut.
OBJECTIVES: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8)

# Hint level 3 or 4 makes a correct answer "met with support" (FR-7.2).
SUPPORT_LEVEL = 3

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
    """Give a badge, or raise an objective badge from bronze to gold. Never lowers or removes."""
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
    elif held.tier == "bronze" and tier == "gold":
        held.tier = "gold"
        held.upgraded_at = datetime.now(UTC)
        held.seen_at = None  # announce the upgrade
    else:
        return Earned()
    session.flush()
    return Earned(badges=(held,))


def on_attempt(session: Session, attempt: Attempt) -> Earned:
    """Points for an activity's first correct answer: fewer if it came after hint level 3 or 4
    (FR-9.2). A wrong answer, or a correct one to an activity already rewarded, earns nothing."""
    if not attempt.correct:
        return Earned()
    supported = attempt.hint_level >= SUPPORT_LEVEL
    event = "activity_correct_supported" if supported else "activity_correct"
    return _add_points(session, attempt.user_id, event, f"activity:{attempt.activity_id}")


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
    """A bonus quest finished (#31): its points and its own badge, and All Quests with the last."""
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
