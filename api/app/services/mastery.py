"""The mastery check (SE document FR-7.1 to FR-7.4, FR-7.6; ID document §3.2 and Table 1).

Each objective's result comes from the student's answers to the module 6 items tagged with it
(`purpose` "mastery"). Only the **first** attempt at each item counts: these items are unseen and
answered once, so trying again until it is right is not evidence. A student who doesn't meet an
objective gets the review path and fresh items for it (FR-7.5, #23), not another go at these.

The objective's rule (`pass_fraction` or `max_wrong` on the Objective, from the criterion in
Table 1) is counted over the parts of those attempts: an option for multiple choice, a step of a
trace table, a pair in a matching item, a line or blank in code. The result is then:

- **met independently** if the rule is met counting only answers given before hint level 3 or 4
  (an answer given after them counts as wrong here),
- **met with support** if it is only met when those answers count too,
- **not yet** if it isn't met either way,
- **not attempted** until every one of the objective's items has been answered.

Everything here is worked out from attempts, so a changed rule or item is applied by running it
again (FR-7.6): `recompute` after each mastery attempt, `recompute_all` on every seed. The report
(`report`) works it out on each request, so it always follows the current rules.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Objective, ObjectiveResult
from app.services import rewards

State = Literal["not_attempted", "met_independently", "met_with_support", "not_yet"]

MASTERY_MODULE = 6  # module 6 is the mastery check (FR-7.1)
SUPPORT_LEVEL = rewards.SUPPORT_LEVEL  # hint 3 or 4 makes a correct answer "with support"
MET: tuple[State, ...] = ("met_independently", "met_with_support")

# The rewards service names the results more briefly (app/services/rewards.py).
_REWARD_NAMES: dict[State, rewards.Mastery] = {
    "met_independently": "independent",
    "met_with_support": "supported",
    "not_yet": "not_yet",
}


@dataclass(frozen=True)
class Rule:
    """An objective's success criterion as a count over parts. One of the two is set."""

    pass_fraction: float | None = None
    max_wrong: int | None = None

    def met(self, right: int, total: int) -> bool:
        if self.max_wrong is not None:
            return total - right <= self.max_wrong
        # A whole-number comparison, so 4 of 5 meets 0.8 whatever the float rounding.
        return right * 1_000_000 >= round((self.pass_fraction or 1.0) * 1_000_000) * total


@dataclass(frozen=True)
class Answer:
    """The first attempt at one item: which of its parts were right, and the hint level seen."""

    attempt_id: int
    parts: tuple[bool, ...]
    hint_level: int


def decide(rule: Rule, answers: Sequence[Answer | None]) -> State:
    """The result for one objective, from its items' first attempts (None: not answered yet)."""
    if not answers or any(a is None for a in answers):
        return "not_attempted"
    given = [a for a in answers if a is not None]
    total = sum(len(a.parts) for a in given)
    unaided = sum(sum(a.parts) for a in given if a.hint_level < SUPPORT_LEVEL)
    if rule.met(unaided, total):
        return "met_independently"
    if rule.met(sum(sum(a.parts) for a in given), total):
        return "met_with_support"
    return "not_yet"


def _parts(attempt: Attempt) -> tuple[bool, ...]:
    """The graded parts the checker stored in `detail`; the whole answer if it stored none."""
    parts: list[dict[str, Any]] = attempt.detail.get("parts") or []
    return tuple(bool(p.get("correct")) for p in parts) or (attempt.correct,)


@dataclass(frozen=True)
class Outcome:
    """One objective's result for one student, and how far through its items they are."""

    objective: Objective
    state: State
    answered: int
    total: int
    evidence: tuple[int, ...]  # the attempts it was decided from


def evaluate(session: Session, user_id: int) -> list[Outcome]:
    """This student's result on every objective, in objective order. Reads only."""
    objectives = session.scalars(select(Objective).order_by(Objective.id)).all()
    items = session.scalars(
        select(Activity)
        .where(Activity.purpose == "mastery", Activity.module_id == MASTERY_MODULE)
        .order_by(Activity.id)
    ).all()
    first_ids = (
        select(func.min(Attempt.id))
        .where(Attempt.user_id == user_id, Attempt.activity_id.in_([i.id for i in items]))
        .group_by(Attempt.activity_id)
    )
    first = {
        a.activity_id: a for a in session.scalars(select(Attempt).where(Attempt.id.in_(first_ids)))
    }

    outcomes = []
    for objective in objectives:
        mine = [i for i in items if i.objective_id == objective.id]
        answers = [
            Answer(a.id, _parts(a), a.hint_level) if (a := first.get(i.id)) else None for i in mine
        ]
        rule = Rule(objective.pass_fraction, objective.max_wrong)
        given = tuple(a.attempt_id for a in answers if a is not None)
        outcomes.append(Outcome(objective, decide(rule, answers), len(given), len(mine), given))
    return outcomes


def is_ready(outcomes: Sequence[Outcome]) -> bool:
    """Ready for the lecture: every objective met, with or without support (FR-7.4)."""
    return bool(outcomes) and all(o.state in MET for o in outcomes)


def recompute(session: Session, user_id: int) -> list[Outcome]:
    """Work out this student's results again and store them (not committed). A result that is
    newly met earns its points and badge (app/services/rewards.py), which are never taken back,
    even if a later rule change lowers the result."""
    outcomes = evaluate(session, user_id)
    stored = {
        r.objective_id: r
        for r in session.scalars(select(ObjectiveResult).where(ObjectiveResult.user_id == user_id))
    }
    results = {o.objective.id: _REWARD_NAMES[o.state] for o in outcomes if o.state in _REWARD_NAMES}
    for o in outcomes:
        row = stored.get(o.objective.id)
        if row is None:
            row = ObjectiveResult(user_id=user_id, objective_id=o.objective.id)
            session.add(row)
        elif row.state == o.state and row.evidence == list(o.evidence):
            continue
        changed = row.state != o.state
        row.state = o.state
        row.evidence = list(o.evidence)
        if changed and o.state in MET:
            rewards.on_objective_result(
                session,
                user_id,
                o.objective.id,
                _REWARD_NAMES[o.state],
                results,
                objectives=[x.objective.id for x in outcomes],
            )
    session.flush()
    return outcomes


def recompute_all(session: Session) -> int:
    """Recompute every student who has answered a mastery item or has a stored result, after the
    rules or items changed (the seed calls this). Returns how many students. Not committed."""
    answered = (
        select(Attempt.user_id)
        .join(Activity, Activity.id == Attempt.activity_id)
        .where(Activity.purpose == "mastery")
    )
    users = set(session.scalars(answered)) | set(session.scalars(select(ObjectiveResult.user_id)))
    for user_id in sorted(users):
        recompute(session, user_id)
    return len(users)
