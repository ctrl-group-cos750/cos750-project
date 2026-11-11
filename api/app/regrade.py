"""`python -m app.regrade [--apply]`: grade stored Parsons and fix-the-bug attempts again with
today's checker, once, after the change that accepts every correct order (#145, FR-5.4, FR-5.5).

Before #145 an attempt was graded against one order, position by position: a correct program in
another order was stored as wrong, and one misplaced line made every later line wrong. Those rows
keep deciding objective results (only the first attempt at a mastery item counts, FR-7.1), so this
re-runs `check_activity` on each attempt's stored `submitted` and, where the result differs,
updates `correct`, `score` and `detail`, then recomputes every student's results
(`mastery.recompute_all`).

- **Dry run by default.** It makes every change inside a transaction, prints what changed, and
  rolls back. `--apply` commits. Run the dry run first and read the counts.
- **Never lowers.** An attempt stored as correct that would now be wrong (its content was edited
  since) is left as it is and counted as "kept". Points and badges are never taken back
  (app/services/rewards.py); an attempt that becomes correct earns the points a first correct
  answer would have, once.
- **Idempotent.** A second run finds nothing to change.
- **Private.** The report names attempts, activities and students by id only, never by email.

No migration: it only updates rows that exist. It does not touch other kinds.
"""

import argparse
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, ObjectiveResult
from app.services import mastery, rewards
from app.services.checking import check_activity

KINDS = ("parsons", "fix_the_bug")


@dataclass
class Report:
    """What a run changed (or, in a dry run, would change)."""

    changed: list[tuple[int, int, int, bool]] = field(default_factory=list)
    """(attempt, user, activity, now correct) for each attempt updated."""
    kept: list[int] = field(default_factory=list)  # stored correct, would now be wrong: left as is
    unreadable: list[int] = field(default_factory=list)  # stored in a shape the checker refuses
    results: list[tuple[int, int, str, str]] = field(default_factory=list)
    """(user, objective, before, after) for each objective result that changed."""

    def lines(self) -> list[str]:
        """The report as text, ids only."""
        out = [
            f"attempts re-graded: {len(self.changed)}, "
            f"now correct: {sum(1 for c in self.changed if c[3])}, "
            f"kept (would be lowered): {len(self.kept)}, unreadable: {len(self.unreadable)}"
        ]
        by_activity: Counter[int] = Counter(c[2] for c in self.changed)
        now_right: Counter[int] = Counter(c[2] for c in self.changed if c[3])
        out += [
            f"  activity {a}: {n} attempts, {now_right[a]} now correct"
            for a, n in sorted(by_activity.items())
        ]
        by_user: defaultdict[int, list[int]] = defaultdict(list)
        for attempt, user, _, _ in self.changed:
            by_user[user].append(attempt)
        out += [f"  user {u}: attempts {ids}" for u, ids in sorted(by_user.items())]
        out.append(f"objective results changed: {len(self.results)}")
        out += [
            f"  user {u}, objective {o}: {before} -> {after}"
            for u, o, before, after in self.results
        ]
        if self.kept:
            out.append(f"kept: attempts {self.kept}")
        if self.unreadable:
            out.append(f"unreadable: attempts {self.unreadable}")
        return out


def _states(session: Session) -> dict[tuple[int, int], str]:
    rows = session.scalars(select(ObjectiveResult))
    return {(r.user_id, r.objective_id): r.state for r in rows}


def regrade(session: Session) -> Report:
    """Re-grade every Parsons and fix-the-bug attempt and recompute results, in `session`
    (not committed: the caller commits or rolls back)."""
    report = Report()
    before = _states(session)
    rows = session.execute(
        select(Attempt, Activity)
        .join(Activity, Activity.id == Attempt.activity_id)
        .where(Activity.kind.in_(KINDS))
        .order_by(Attempt.id)
    ).all()
    for attempt, activity in rows:
        try:
            result = check_activity(
                activity.kind, activity.config, activity.solution, attempt.submitted
            )
        except (ValidationError, ValueError):
            report.unreadable.append(attempt.id)
            continue
        detail = result.model_dump()
        if (attempt.correct, attempt.score, attempt.detail) == (
            result.correct,
            result.score,
            detail,
        ):
            continue
        if attempt.correct and not result.correct:
            report.kept.append(attempt.id)
            continue
        became_correct = result.correct and not attempt.correct
        attempt.correct, attempt.score, attempt.detail = result.correct, result.score, detail
        session.flush()
        if became_correct:
            rewards.on_attempt(session, attempt)  # once per activity: points are keyed by ref
        report.changed.append((attempt.id, attempt.user_id, activity.id, result.correct))
    mastery.recompute_all(session)
    session.flush()
    after = _states(session)
    report.results = [
        (user, objective, before.get((user, objective), "not_attempted"), state)
        for (user, objective), state in sorted(after.items())
        if before.get((user, objective), "not_attempted") != state
    ]
    return report


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.regrade", description=__doc__)
    parser.add_argument("--apply", action="store_true", help="commit (default: a dry run)")
    args = parser.parse_args(argv)
    from app.db import SessionLocal  # here, so importing this module opens no database

    with SessionLocal() as session:
        report = regrade(session)
        for line in report.lines():
            print(line)
        if args.apply:
            session.commit()
            print("applied")
        else:
            session.rollback()
            print("dry run: nothing written (run again with --apply to write)")


if __name__ == "__main__":
    main()
