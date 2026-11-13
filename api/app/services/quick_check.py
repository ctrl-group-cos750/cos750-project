"""A module's quick check: "Already know this?" (SE document FR-8.2, issue #214).

Modules 1 to 5 each have a quick check of `QUICK_CHECK_SIZE` multiple choice questions (activities
of purpose `test_out`, one per objective the module teaches where it can). A student who thinks
they know a module already takes it instead of working through the module. Novices often misjudge
what they know, so skipping goes through the check rather than a button (ID document §7.5).

- **One answer each, no hints, results at the end.** The questions are answered together on one
  page and sent at once; nothing is marked until then. The activity routes refuse these items
  (app/services/access.py), so they can't be answered, hinted at or read one by one.
- **Pass:** at least `PASS_MARK` right, so at most one wrong. With four options a question, blind
  guessing passes about 5% of the time. The module is marked `tested_out` (`ModuleProgress.status`),
  which counts as done wherever "complete" does for opening the mastery check and for the
  recommended next module. It stays open, and working through it to the end still completes it.
- **Fail:** nothing is taken away or locked. The result names what was missed and suggests where to
  go: with at most one right, the module before this one if it isn't done (`start_with`); otherwise
  the earliest module before this one that teaches the first missed objective, if it isn't done;
  otherwise this module (`work_through`).
- **One attempt per module.** A second try would be the same four questions, already marked; after
  a fail the module itself is the way on. Nor can a module completed by working through it be
  tested out afterwards. "Taken" means a `quick_check_taken` event exists for the module, logged
  in the same transaction as the answers. Answers to its items alone don't count: items 103, 203,
  314, 403 and 503 were ordinary questions before they became quick-check items, so a student may
  have answered one by its address back then, and that must not use up the check (#215 review).
  The result is read from each item's latest answer, which is the quick check's: the items can't
  be answered anywhere else since.
- **Two sends at once** (a double click) mark it once: the second waits for the first and is
  refused as taken. On Postgres the student's row lock does that; SQLite, which has no row locks,
  takes its database write lock at the start instead (`claim_writes`).
- **It counts for nothing else.** Testing out earns no module points and no First Module badge (that
  is for working through a module), and the answers recorded earn no activity points, decide no
  objective result and mark no segment done: these items are in no segment and count towards no
  objective result (app/services/mastery.py `counts`). The attempts are kept for the evaluation.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Event, Module, ModuleProgress, Segment
from app.schemas.activities import MultipleChoiceConfig, MultipleChoiceSolution
from app.schemas.modules import (
    QuickCheckItemResultOut,
    QuickCheckOptionOut,
    QuickCheckOut,
    QuickCheckQuestionOut,
    QuickCheckResultOut,
    QuickCheckScoreOut,
    QuickCheckState,
)
from app.services.checking import check_activity
from app.services.events import log_event
from app.services.locks import claim_writes, lock_student

QUICK_CHECK_SIZE = 4
PASS_MARK = QUICK_CHECK_SIZE - 1  # all right, or all but one
DONE: frozenset[str] = frozenset({"complete", "tested_out"})


class QuickCheckMissing(ValueError):
    """The module has no quick check (module 0, module 6, or no module with this id)."""


class QuickCheckTaken(ValueError):
    """The student has taken this module's quick check already: one attempt per module."""


class ModuleAlreadyDone(ValueError):
    """The student completed the module by working through it, so there is nothing to test out of."""


class AnswersDontFit(ValueError):
    """The answers aren't exactly one for each question, or name an option a question doesn't have."""


@dataclass(frozen=True)
class Answer:
    activity_id: int
    selected: str


def items(session: Session, module_id: int) -> Sequence[Activity]:
    """The module's quick check questions, in id order."""
    return session.scalars(
        select(Activity)
        .where(Activity.module_id == module_id, Activity.purpose == "test_out")
        .order_by(Activity.id)
    ).all()


def _attempts(session: Session, user_id: int, ids: Sequence[int]) -> dict[int, Attempt]:
    """The student's latest attempt at each of these items: for a taken quick check, its answer
    (see the module docstring)."""
    latest: dict[int, Attempt] = {}
    for attempt in session.scalars(
        select(Attempt)
        .where(Attempt.user_id == user_id, Attempt.activity_id.in_(ids))
        .order_by(Attempt.id)
    ):
        latest[attempt.activity_id] = attempt
    return latest


def taken(session: Session, user_id: int) -> set[int]:
    """The modules whose quick check this student has taken: those with a `quick_check_taken`
    event (see the module docstring)."""
    refs = session.scalars(
        select(Event.ref).where(Event.user_id == user_id, Event.type == "quick_check_taken")
    )
    return {int(ref.removeprefix("module:")) for ref in refs if ref.startswith("module:")}


def _by_module(session: Session) -> dict[int, list[int]]:
    """Each module's quick check items, in id order."""
    out: dict[int, list[int]] = {}
    for activity_id, module_id in session.execute(
        select(Activity.id, Activity.module_id)
        .where(Activity.purpose == "test_out")
        .order_by(Activity.id)
    ):
        if module_id is not None:
            out.setdefault(module_id, []).append(activity_id)
    return out


def scores(session: Session, user_id: int) -> dict[int, QuickCheckScoreOut]:
    """How each quick check this student has taken went: right answers out of its items."""
    done = taken(session, user_id)
    if not done:
        return {}
    by_module = {m: ids for m, ids in _by_module(session).items() if m in done}
    attempts = _attempts(session, user_id, [i for ids in by_module.values() for i in ids])
    return {
        module_id: QuickCheckScoreOut(
            correct=sum(1 for i in ids if i in attempts and attempts[i].correct),
            total=len(ids),
        )
        for module_id, ids in by_module.items()
    }


def passed(session: Session, user_id: int) -> set[int]:
    """The modules whose quick check this student passed. Kept whatever happens to the module
    later: working through it after testing out still counts the pass (skills.py's medals)."""
    return {m for m, score in scores(session, user_id).items() if score.correct >= PASS_MARK}


def states(
    session: Session, user_id: int, statuses: dict[int, str]
) -> dict[int, QuickCheckState | None]:
    """Each module's quick check state for the map, given the modules' statuses."""
    by_module = _by_module(session)
    results = scores(session, user_id)
    out: dict[int, QuickCheckState | None] = {}
    for module_id, status in statuses.items():
        if not by_module.get(module_id):
            out[module_id] = None
        elif module_id in results:
            right = results[module_id].correct
            out[module_id] = "passed" if right >= PASS_MARK else "not_passed"
        elif status in DONE or status == "locked":
            out[module_id] = None
        else:
            out[module_id] = "available"
    return out


def _done_modules(session: Session, user_id: int) -> set[int]:
    return set(
        session.scalars(
            select(ModuleProgress.module_id).where(
                ModuleProgress.user_id == user_id, ModuleProgress.status.in_(DONE)
            )
        )
    )


def _ordered_modules(session: Session) -> list[int]:
    """The modules with content, in map order."""
    with_content = set(
        session.scalars(select(Segment.module_id).where(Segment.module_id.isnot(None)))
    )
    return [
        m for m in session.scalars(select(Module.id).order_by(Module.position)) if m in with_content
    ]


def _first_teaching(session: Session, objective_id: int, order: list[int]) -> int | None:
    """The first module in map order whose segments practise this objective."""
    teaching = set(
        session.scalars(
            select(Segment.module_id)
            .join(Activity, Activity.id == Segment.activity_id)
            .where(
                Activity.objective_id == objective_id,
                Activity.purpose == "practice",
                Segment.module_id.isnot(None),
                Segment.support_for.is_(None),
            )
        )
    )
    return next((m for m in order if m in teaching), None)


def _suggest(
    session: Session, user_id: int, module_id: int, right: int, missed: list[Activity]
) -> tuple[Literal["move_on", "start_with", "work_through"], int | None]:
    order = _ordered_modules(session)
    done = _done_modules(session, user_id)
    here = order.index(module_id) if module_id in order else len(order)
    if right >= PASS_MARK:
        after = next((m for m in order[here + 1 :] if m not in done), None)
        return "move_on", after
    before = order[here - 1] if here > 0 else None
    if right <= 1 and before is not None and before not in done:
        return "start_with", before
    first_missed = next((a.objective_id for a in missed if a.objective_id is not None), None)
    if first_missed is not None:
        teaches = _first_teaching(session, first_missed, order[:here])
        if teaches is not None and teaches not in done:
            return "start_with", teaches
    return "work_through", module_id


def _label(config: MultipleChoiceConfig, option: str) -> str:
    return next((o.label for o in config.options if o.id == option), option)


def _result(
    session: Session, user_id: int, module_id: int, questions: Sequence[Activity]
) -> QuickCheckResultOut | None:
    attempts = _attempts(session, user_id, [a.id for a in questions])
    if not questions or any(a.id not in attempts for a in questions):
        return None
    out: list[QuickCheckItemResultOut] = []
    for activity in questions:
        config = MultipleChoiceConfig.model_validate(activity.config)
        solution = MultipleChoiceSolution.model_validate(activity.solution)
        attempt = attempts[activity.id]
        out.append(
            QuickCheckItemResultOut(
                activity_id=activity.id,
                title=activity.title,
                prompt=config.prompt,
                correct=attempt.correct,
                chosen=_label(config, str(attempt.submitted.get("selected", ""))),
                answer=_label(config, solution.correct),
                explanation=solution.explanation or "",
            )
        )
    right = sum(item.correct for item in out)
    missed = [a for a, item in zip(questions, out, strict=True) if not item.correct]
    suggestion, suggested = _suggest(session, user_id, module_id, right, missed)
    return QuickCheckResultOut(
        passed=right >= PASS_MARK,
        correct=right,
        total=len(out),
        suggestion=suggestion,
        suggested_module=suggested,
        look_at=[a.title for a in missed],
        items=out,
    )


def _progress(session: Session, user_id: int, module_id: int) -> ModuleProgress | None:
    return session.scalar(
        select(ModuleProgress).where(
            ModuleProgress.user_id == user_id, ModuleProgress.module_id == module_id
        )
    )


def quick_check(session: Session, user_id: int, module_id: int) -> QuickCheckOut:
    """The module's quick check for this student: its questions while they may take it, or how
    it went once taken. Raises `QuickCheckMissing`."""
    questions = items(session, module_id)
    if not questions:
        raise QuickCheckMissing(module_id)
    was_taken = module_id in taken(session, user_id)
    result = _result(session, user_id, module_id, questions) if was_taken else None
    row = _progress(session, user_id, module_id)
    available = not was_taken and (row is None or row.status not in DONE)
    return QuickCheckOut(
        module_id=module_id,
        available=available,
        pass_mark=PASS_MARK,
        questions=[
            QuickCheckQuestionOut(
                id=a.id,
                title=a.title,
                prompt=(config := MultipleChoiceConfig.model_validate(a.config)).prompt,
                options=[QuickCheckOptionOut(id=o.id, label=o.label) for o in config.options],
            )
            for a in questions
        ]
        if available
        else [],
        result=result,
    )


def take(
    session: Session, user_id: int, module_id: int, answers: Sequence[Answer]
) -> QuickCheckResultOut:
    """Mark the student's answers, one for each question, and record them (not committed). A pass
    marks the module tested out. Raises `QuickCheckMissing`, `QuickCheckTaken`,
    `ModuleAlreadyDone` or `AnswersDontFit`; nothing is recorded then."""
    # Two sends at once: the second waits for the first, then sees it taken (module docstring).
    claim_writes(session)
    lock_student(session, user_id)
    questions = items(session, module_id)
    if not questions:
        raise QuickCheckMissing(module_id)
    if module_id in taken(session, user_id):
        raise QuickCheckTaken(module_id)
    row = _progress(session, user_id, module_id)
    if row is not None and row.status in DONE:
        raise ModuleAlreadyDone(module_id)
    chosen = {answer.activity_id: answer.selected for answer in answers}
    if len(chosen) != len(answers) or set(chosen) != {a.id for a in questions}:
        raise AnswersDontFit(module_id)
    for activity in questions:
        options = {o.id for o in MultipleChoiceConfig.model_validate(activity.config).options}
        if chosen[activity.id] not in options:
            raise AnswersDontFit(module_id)
    right = 0
    for activity in questions:
        submitted = {"selected": chosen[activity.id]}
        result = check_activity(activity.kind, activity.config, activity.solution, submitted)
        right += result.correct
        session.add(
            Attempt(
                user_id=user_id,
                activity_id=activity.id,
                submitted=submitted,
                correct=result.correct,
                score=result.score,
                detail=result.model_dump(),
                hint_level=0,
            )
        )
    passed = right >= PASS_MARK
    if passed:
        if row is None:
            row = ModuleProgress(user_id=user_id, module_id=module_id, current_segment_position=0)
            session.add(row)
        row.status = "tested_out"
        row.completed_at = datetime.now(tz=UTC)
    log_event(
        session,
        user_id,
        "quick_check_taken",
        f"module:{module_id}",
        {"correct": right, "total": len(questions), "passed": passed},
    )
    session.flush()
    result_out = _result(session, user_id, module_id, questions)
    if result_out is None:  # every question was answered just above
        raise AnswersDontFit(module_id)
    return result_out


def refresh_tested_out(session: Session, user_id: int) -> list[int]:
    """After a re-grade changed quick check answers (app/regrade.py): mark tested out each module
    whose quick check now passes and that isn't complete or tested out yet, as `take` would have.
    A re-grade never lowers an answer, so a pass can't become a fail, and nothing is taken away.
    Not committed. Returns the modules it marked."""
    marked = []
    for module_id in sorted(passed(session, user_id)):
        row = _progress(session, user_id, module_id)
        if row is not None and row.status in DONE:
            continue
        if row is None:
            row = ModuleProgress(user_id=user_id, module_id=module_id, current_segment_position=0)
            session.add(row)
        row.status = "tested_out"
        row.completed_at = datetime.now(tz=UTC)
        marked.append(module_id)
    session.flush()
    return marked
