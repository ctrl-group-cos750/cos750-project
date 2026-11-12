"""The mastery check (SE document FR-7.1 to FR-7.4, FR-7.6; ID document §3.2 and Table 1).

Each objective's result comes from the student's answers to the module 6 items tagged with it
(`purpose` "mastery"). Only the **first** attempt at each item counts: these items are unseen and
answered once, so trying again until it is right is not evidence.

A student whom module 6 marks "not yet" on an objective gets its **review path** instead (FR-7.5,
ID document §7.6): segments that teach it again, practice with the full hint ladder, then fresh
mastery items for that objective only. Once every fresh item is answered, they decide the result
by the same rule, and the module 6 result no longer does. The path opens only for a "not yet"
objective, so its fresh items stay unseen until then (`review_open`), and there is one path per
objective: a student still "not yet" after it is told to bring that objective to the lecture.

The objective's rule (`pass_fraction` or `max_wrong` on the Objective, from the criterion in
Table 1) is counted over the parts of those attempts: an option for multiple choice, a step of a
trace table, a pair in a matching item, a line or blank in code. The result is then:

- **met independently** if the rule is met counting only answers given before hint level 3 or 4
  (an answer given after them counts as wrong here),
- **met with support** if it is only met when those answers count too,
- **not yet** if it isn't met either way,
- **not attempted** until every one of the objective's items has been answered.

Module 6 is one check, marked at the end (#144): no result is shown for any objective, and no
points or badges are given for its items, until the student has answered **every** module 6 item
(`check_finished`). Until then each objective reads "not attempted", so neither the report nor a
badge gives away whether an earlier answer was right. The attempt response says nothing about it
either (app/routers/activities.py), and each item takes one answer only.

Everything here is worked out from attempts, so a changed rule or item is applied by running it
again (FR-7.6): `recompute` after each mastery attempt, `recompute_all` on every seed. The report
(GET /api/me/report) calls `evaluate` on each request, so it always follows the current rules.
`recompute` also stores the results in `objective_results`, for two things the report doesn't do:
noticing that a result changed, which is what earns its badge and points, and the evaluation
export (FR-10).

The three results go by three spellings: `met_independently` here and in the API (the SE document's
data model), `independent` in app/services/rewards.py, and `independent` / `not-yet` in the
frontend's MasteryStatus. `_REWARD_NAMES` maps the first to the second; the frontend maps the rest.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Objective, ObjectiveResult, Segment
from app.services import rewards
from app.services.events import log_event
from app.services.locks import lock_student

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


def counts(activity: Activity) -> bool:
    """Whether answers to this activity decide a result: a mastery item in module 6 (FR-7.1), or
    a fresh mastery item on a review path, which has no module (FR-7.5). The seed refuses a
    mastery item anywhere else."""
    return activity.purpose == "mastery" and activity.module_id in (MASTERY_MODULE, None)


def in_check(activity: Activity) -> bool:
    """Whether this is one of module 6's mastery items: one answer each, no right or wrong shown
    and hints up to level 2 only, until the check is finished (#144)."""
    return activity.purpose == "mastery" and activity.module_id == MASTERY_MODULE


def _counted() -> ColumnElement[bool]:
    """`counts` as a query condition."""
    return and_(
        Activity.purpose == "mastery",
        or_(Activity.module_id == MASTERY_MODULE, Activity.module_id.is_(None)),
    )


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
class Tally:
    """One set of items (module 6's, or a review path's fresh ones) and what they decide."""

    state: State
    answered: int
    total: int
    evidence: tuple[int, ...]  # the first attempts it was decided from


@dataclass(frozen=True)
class Outcome:
    """One objective's result for one student. `check` is module 6; `review` is the review path's
    fresh items, present once the path is open (module 6 said "not yet")."""

    objective: Objective
    check: Tally
    review: Tally | None

    @property
    def via_review(self) -> bool:
        """The review path decided the result: all its fresh items are answered."""
        return self.review is not None and self.review.state != "not_attempted"

    @property
    def state(self) -> State:
        return (
            self.review.state if self.review is not None and self.via_review else self.check.state
        )

    @property
    def evidence(self) -> tuple[int, ...]:
        return self.check.evidence + (self.review.evidence if self.review else ())


def _tally(rule: Rule, items: Sequence[Activity], first: dict[int, Attempt]) -> Tally:
    answers = [
        Answer(a.id, _parts(a), a.hint_level) if (a := first.get(i.id)) else None for i in items
    ]
    given = tuple(a.attempt_id for a in answers if a is not None)
    return Tally(decide(rule, answers), len(given), len(items), given)


def review_items(session: Session) -> dict[int, list[Activity]]:
    """Each objective's fresh review-path items, in path order."""
    rows = session.execute(
        select(Segment, Activity)
        .join(Activity, Activity.id == Segment.activity_id)
        .where(Segment.review_objective_id.is_not(None), Activity.purpose == "mastery")
        .order_by(Segment.position)
    ).all()
    found: dict[int, list[Activity]] = {}
    for segment, activity in rows:
        objective_id = cast(int, segment.review_objective_id)  # not None, by the query
        found.setdefault(objective_id, []).append(activity)
    return found


def _check_items(session: Session) -> Sequence[Activity]:
    """Module 6's mastery items, in id order."""
    return session.scalars(
        select(Activity)
        .where(Activity.purpose == "mastery", Activity.module_id == MASTERY_MODULE)
        .order_by(Activity.id)
    ).all()


def _first_attempts(session: Session, user_id: int, ids: Sequence[int]) -> dict[int, Attempt]:
    """This student's first attempt at each of these activities, by activity id."""
    first_ids = (
        select(func.min(Attempt.id))
        .where(Attempt.user_id == user_id, Attempt.activity_id.in_(ids))
        .group_by(Attempt.activity_id)
    )
    return {
        a.activity_id: a for a in session.scalars(select(Attempt).where(Attempt.id.in_(first_ids)))
    }


def check_finished(session: Session, user_id: int) -> bool:
    """Whether this student has answered every module 6 item: the check is over, and its results
    can be shown (#144)."""
    items = [i.id for i in _check_items(session)]
    answered = set(
        session.scalars(
            select(Attempt.activity_id).where(
                Attempt.user_id == user_id, Attempt.activity_id.in_(items)
            )
        )
    )
    return bool(items) and answered >= set(items)


def evaluate(session: Session, user_id: int) -> list[Outcome]:
    """This student's result on every objective, in objective order. Reads only."""
    objectives = session.scalars(select(Objective).order_by(Objective.id)).all()
    check = _check_items(session)
    fresh = review_items(session)
    ids = [i.id for i in check] + [i.id for items in fresh.values() for i in items]
    first = _first_attempts(session, user_id, ids)
    finished = bool(check) and all(i.id in first for i in check)

    outcomes = []
    for objective in objectives:
        rule = Rule(objective.pass_fraction, objective.max_wrong)
        on_check = _tally(rule, [i for i in check if i.objective_id == objective.id], first)
        if not finished:  # nothing is marked until the whole check is answered (#144)
            on_check = Tally("not_attempted", on_check.answered, on_check.total, on_check.evidence)
        review = None
        if on_check.state == "not_yet":
            review = _tally(rule, fresh.get(objective.id, []), first)
        outcomes.append(Outcome(objective, on_check, review))
    return outcomes


def review_open(session: Session, user_id: int, objective_id: int) -> bool:
    """Whether this student's review path for the objective is open: module 6 said "not yet"."""
    return any(
        o.objective.id == objective_id and o.review is not None for o in evaluate(session, user_id)
    )


def is_ready(outcomes: Sequence[Outcome]) -> bool:
    """Ready for the lecture: every objective met, with or without support (FR-7.4). The ID
    document puts it as "no objective marked Not yet"; an objective not attempted yet isn't met
    either, or a student who had answered nothing would be ready."""
    return bool(outcomes) and all(o.state in MET for o in outcomes)


def recompute(session: Session, user_id: int) -> list[Outcome]:
    """Work out this student's results again and store them (not committed). A result that is
    newly met earns its points and badge (app/services/rewards.py), which are never taken back,
    even if a later rule change lowers the result."""
    # One recompute per student at a time: two answers submitted together would otherwise both
    # insert the first result rows and one would fail on the unique constraint. An answer takes
    # this lock before its insert (app/services/attempts.py); taking it here as well covers a
    # recompute on its own (the seed's `recompute_all`, after a rule change). It is FOR NO KEY
    # UPDATE: a plain FOR UPDATE conflicts with the KEY SHARE lock that inserting a row which
    # references the student takes (app/services/locks.py).
    lock_student(session, user_id)
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
        before = row.state or "not_attempted"  # where every student starts
        if before != o.state:
            log_event(
                session,
                user_id,
                "result_changed",
                f"objective:{o.objective.id}",
                {"from": before, "to": o.state, "viaReview": o.via_review},
            )
        row.state = o.state
        row.evidence = list(o.evidence)
        if changed and o.state in MET:
            rewards.on_objective_result(
                session,
                user_id,
                o.objective.id,
                _REWARD_NAMES[o.state],
                results,
                via_review=o.via_review,  # Came Back Stronger
                objectives=[x.objective.id for x in outcomes],
            )
    # A module 6 item's points wait for the end of the check, like its result (#144): given now,
    # they would say which answers were right. Points are given once, so this is safe to repeat.
    if check_finished(session, user_id):
        evidence = [i for o in outcomes for i in o.check.evidence]
        for attempt in session.scalars(select(Attempt).where(Attempt.id.in_(evidence))):
            rewards.on_attempt(session, attempt)
    session.flush()
    return outcomes


def recompute_all(session: Session) -> int:
    """Recompute every student who has answered a mastery item or has a stored result, after the
    rules or items changed (the seed calls this). Returns how many students. Not committed."""
    answered = (
        select(Attempt.user_id).join(Activity, Activity.id == Attempt.activity_id).where(_counted())
    )
    users = set(session.scalars(answered)) | set(session.scalars(select(ObjectiveResult.user_id)))
    for user_id in sorted(users):
        recompute(session, user_id)
    return len(users)
