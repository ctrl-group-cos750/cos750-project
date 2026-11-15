"""`python -m app.regrade [--apply]`: grade stored Parsons and fix-the-bug attempts again with
today's checker, once, after the change that accepts every correct order (#145, FR-5.4, FR-5.5).

Before #145 an attempt was graded against one order, position by position: a correct program in
another order was stored as wrong, and one misplaced line made every later line wrong. Those rows
keep deciding objective results (only the first attempt at a mastery item counts, FR-7.1), so this
re-runs `check_activity` on each attempt's stored `submitted` and, where the result differs,
updates `correct`, `score` and `detail`, then recomputes the results of each student it changed
(`mastery.recompute`).

- **One student at a time, locked.** Students are taken in id order. Each is locked with the
  student write lock every answer, hint and position save takes (`lock_student`,
  app/services/locks.py: `FOR NO KEY UPDATE` on their user row) before any of their rows is read
  or written, so a student answering at the same moment waits for the re-grade of their attempts,
  or the re-grade waits for them, and neither deadlocks. A student deleted since the list was read
  is passed over. With `--apply` each student is committed on their own, so a lock is held only
  briefly.
- **Activities staff have edited are skipped.** An attempt on an activity with `edited_at` set
  (changed in the staff content editor, #128) may answer a different question than the one now
  stored, so it is left as it is and listed as "edited by staff".
- **Dry run by default.** Each student's changes are made, reported and rolled back, so the counts
  are real. `--apply` commits them. Run the dry run first and read the counts.
- **Never lowers.** An attempt stored as correct that would now be wrong (its content was edited
  since) is left as it is and counted as "kept". Points and badges are never taken back
  (app/services/rewards.py); an attempt that becomes correct earns the points a first correct
  answer would have, once.
- **Idempotent.** A second run finds nothing to change.
- **Private.** The report names attempts, activities and students by id only, never by email.

- **Quick checks too** (FR-8.2, #215 review). Answers to quick check questions (purpose
  `test_out`, multiple choice) are re-marked the same way, and a module whose quick check now
  passes is marked tested out, as taking it would have done (`quick_check.refresh_tested_out`).
  They earn nothing, as when taken.

No migration: it only updates rows that exist. It does not touch other kinds. Trace answers in
particular are left as stored: the trace checker's impossible-queue rule (review of 13 Nov, item
618) would only lower marks, and a re-grade never lowers, so results earned before it stand (SE
document FR-6.6, FR-9.6).
"""

import argparse
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from pydantic import ValidationError
from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, ObjectiveResult
from app.services import mastery, quick_check, rewards, skills
from app.services.checking import check_activity
from app.services.locks import StudentGone, lock_student

KINDS = ("parsons", "fix_the_bug")
QUICK_CHECK = "test_out"  # quick check questions, re-marked whatever their kind


def _regraded() -> ColumnElement[bool]:
    """The attempts a re-grade looks at: Parsons and fix-the-bug answers, and quick check ones."""
    return or_(Activity.kind.in_(KINDS), Activity.purpose == QUICK_CHECK)


@dataclass
class Report:
    """What a run changed (or, in a dry run, would change)."""

    changed: list[tuple[int, int, int, bool]] = field(default_factory=list)
    """(attempt, user, activity, now correct) for each attempt updated."""
    kept: list[int] = field(default_factory=list)  # stored correct, would now be wrong: left as is
    unreadable: list[int] = field(default_factory=list)  # stored in a shape the checker refuses
    edited: list[int] = field(default_factory=list)  # activity edited by staff (#128): skipped
    results: list[tuple[int, int, str, str]] = field(default_factory=list)
    """(user, objective, before, after) for each objective result that changed."""
    tested_out: list[tuple[int, int]] = field(default_factory=list)
    """(user, module) for each module now tested out: its quick check passes after a re-grade."""

    def lines(self) -> list[str]:
        """The report as text, ids only."""
        out = [
            f"attempts re-graded: {len(self.changed)}, "
            f"now correct: {sum(1 for c in self.changed if c[3])}, "
            f"kept (would be lowered): {len(self.kept)}, unreadable: {len(self.unreadable)}, "
            f"edited by staff (skipped): {len(self.edited)}"
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
        out.append(f"modules now tested out: {len(self.tested_out)}")
        out += [f"  user {u}, module {m}" for u, m in self.tested_out]
        if self.kept:
            out.append(f"kept: attempts {self.kept}")
        if self.unreadable:
            out.append(f"unreadable: attempts {self.unreadable}")
        if self.edited:
            out.append(f"edited by staff: attempts {self.edited}")
        return out


def _states(session: Session, user_id: int) -> dict[int, str]:
    rows = session.scalars(select(ObjectiveResult).where(ObjectiveResult.user_id == user_id))
    return {r.objective_id: r.state for r in rows}


def _regrade_student(session: Session, user_id: int, report: Report) -> None:
    """Re-grade one student's attempts and recompute their results, under their lock (the one
    answers take, app/services/locks.py). Raises `StudentGone` if they were deleted."""
    lock_student(session, user_id)
    rows = session.execute(
        select(Attempt, Activity)
        .join(Activity, Activity.id == Attempt.activity_id)
        .where(Attempt.user_id == user_id, _regraded())
        .order_by(Attempt.id)
    ).all()
    changed = False
    quick_check_changed = False
    before: dict[int, str] = {}
    for attempt, activity in rows:
        if activity.edited_at is not None:  # staff changed it: the stored answer may not fit
            report.edited.append(attempt.id)
            continue
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
        if not changed:
            before = _states(session, user_id)
            changed = True
        became_correct = result.correct and not attempt.correct
        attempt.correct, attempt.score, attempt.detail = result.correct, result.score, detail
        session.flush()
        # A quick check answer earns nothing (FR-8.2, #214), so a re-grade gives it nothing either.
        if activity.purpose == QUICK_CHECK:
            quick_check_changed = True
        elif became_correct and not mastery.in_check(activity):
            # Once per activity: points are keyed by ref. A module 6 item's points wait for the
            # end of the check, as when answered (#144): `mastery.recompute` below pays them then.
            rewards.on_attempt(session, attempt)
        report.changed.append((attempt.id, user_id, activity.id, result.correct))
    if quick_check_changed:
        report.tested_out += [
            (user_id, m) for m in quick_check.refresh_tested_out(session, user_id)
        ]
    if changed:
        mastery.recompute(session, user_id)
        # An answer now right can make an objective secure in practice: its Practised badge (#214).
        skills.award_practised(session, user_id)
        session.flush()
        after = _states(session, user_id)
        report.results += [
            (user_id, objective, before.get(objective, "not_attempted"), state)
            for objective, state in sorted(after.items())
            if before.get(objective, "not_attempted") != state
        ]


def regrade(session: Session, after_each: Literal["commit", "rollback"] | None = None) -> Report:
    """Re-grade every Parsons, fix-the-bug and quick check attempt, student by student, and recompute the
    results of the students it changed. `after_each` ends each student's transaction (commit for
    --apply, rollback for a dry run), releasing their lock; None leaves it to the caller."""
    report = Report()
    users = session.scalars(
        select(Attempt.user_id)
        .join(Activity, Activity.id == Attempt.activity_id)
        .where(_regraded())
        .distinct()
        .order_by(Attempt.user_id)
    ).all()
    for user_id in users:
        try:
            _regrade_student(session, user_id, report)
        except StudentGone:  # deleted since the list was read: nothing left to re-grade
            session.rollback()
            continue
        if after_each == "commit":
            session.commit()
        elif after_each == "rollback":
            session.rollback()
    return report


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.regrade", description=__doc__)
    parser.add_argument("--apply", action="store_true", help="commit (default: a dry run)")
    args = parser.parse_args(argv)
    from app.db import SessionLocal  # here, so importing this module opens no database

    with SessionLocal() as session:
        report = regrade(session, "commit" if args.apply else "rollback")
        for line in report.lines():
            print(line)
        if args.apply:
            print("applied")
        else:
            print("dry run: nothing written (run again with --apply to write)")


if __name__ == "__main__":
    main()
