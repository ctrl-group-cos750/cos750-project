"""Seeded demo accounts at different points in the course (SE document FR-1.4), so the demo and the
end-to-end tests can show any stage without working through 75 minutes of content.

Each account is in demo/accounts.json: who it is, the steps that put it at its stage, and what that
stage must look like. A step names questions by where they are, never by id: "answer module 6's
mastery items right, except objective 6's". The seed finds those questions in the order a student
meets them, builds a right or wrong answer from each one's stored solution (a wrong one only from what the
question offers, as a student's would be: never an empty answer, which the API refuses), and
submits it through the same code a student's answers go through (app/services/attempts.py). So new or replaced content
never breaks an account, and every result is the one the real mastery rules work out.

`progress` says how far the account got through each module. The seed walks it through the module
service (app/services/modules.py) one segment at a time, as a student would, so the module map
shows the same stage as the answers. "end" means the whole module, however many segments it has.
A segment must be done before the walk moves past it (FR-2.7), so it answers any activity segment
the steps haven't answered, and passes any video checkpoint, right first time. It runs after the
steps, so the steps' answers stay the first attempts that mastery counts.
A module with no segments yet is passed over, as it is for a student (FR-2.1). If a module is
still locked when the walk reaches it, the walk stops there and the seed says so, rather than
failing: the account goes as far as the course allows.

`expect` says what the account must end up as (ready for the lecture or not, and which objectives
are "not yet"). If content changes so that the steps no longer produce it, the load fails, naming
the account. CI loads the committed accounts against the committed content, so that shows up in
the PR that changed the content, not on a deploy. On a deploy, a demo account problem is reported
and the previous demo accounts are left as they were (app/seed/__main__.py): it never stops the API.

`python -m app.seed` rebuilds the accounts every time it runs (the API container does on every
start), so whatever a rehearsal clicked through is undone by the next seed.

Every demo account shares one password, from DEMO_PASSWORD in the server's environment (Coolify).
It is never committed. Unset, no demo accounts are made: an environment only has them on purpose.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Checkpoint, Module, Segment, User, Video
from app.models.user import DEMO_EMAIL_DOMAIN
from app.passwords import password_problem
from app.schemas.activities import (
    ChooseTestsConfig,
    ChooseTestsSolution,
    FillInConfig,
    FillInSolution,
    FixTheBugConfig,
    FixTheBugSolution,
    MatchingConfig,
    MatchingSolution,
    MultipleChoiceConfig,
    MultipleChoiceSolution,
    ParsonsSolution,
    TraceConfig,
)
from app.schemas.content import Purpose
from app.schemas.graphs import GraphScenarioOut
from app.security import hash_password
from app.services.attempts import hint_level_seen, record_attempt, reveal_next_hint
from app.services.bfs import run_bfs
from app.services.checking import check_activity
from app.services.history import delete_history
from app.services.mastery import evaluate, is_ready
from app.services.modules import ModuleLocked, done_segments, get_module_detail, save_position

DEMO_FILE = Path(__file__).parent / "demo" / "accounts.json"


class DemoStep(BaseModel, extra="forbid"):
    """Answer some of a module's questions, in the order its segments show them."""

    module: int
    # Only questions with one of these purposes, or for one of these objectives. Unset: all.
    purposes: list[Purpose] | None = None
    objectives: list[int] | None = None
    except_objectives: list[int] = Field(default_factory=list)
    # Only the first this many of them, e.g. to stop partway through a module.
    limit: int | None = Field(default=None, ge=1)
    answer: Literal["right", "wrong"]
    # Hints to reveal before answering, up to as many as each question has. 3 or 4 makes a right
    # answer "with support" (FR-7.2).
    hints: int = Field(default=0, ge=0, le=4)


class DemoProgress(BaseModel, extra="forbid"):
    """How far the account got through one module (FR-2.5)."""

    module: int
    # "end" completes the module, however many segments it has. A number stops partway, at that
    # segment (1 is the first). A stop the module can no longer hold, at or past its last segment,
    # fails the load rather than quietly completing the module.
    through: Literal["end"] | Annotated[int, Field(ge=1)] = "end"


class DemoExpect(BaseModel, extra="forbid"):
    """What the account's mastery report must say once its steps are done (FR-7.3, FR-7.4)."""

    ready: bool
    not_yet: list[int] = Field(default_factory=list)  # exactly these objectives are "not yet"


class DemoAccount(BaseModel, extra="forbid"):
    # The email's local part: "new" is new@demo.example.com.
    key: str = Field(pattern=r"^[a-z][a-z0-9-]{0,30}$")
    display_name: str = Field(min_length=1, max_length=50)
    # Where in the course this account is, for whoever runs the demo.
    stage: str = Field(min_length=1)
    staff: bool = False
    progress: list[DemoProgress] = Field(default_factory=list)
    steps: list[DemoStep] = Field(default_factory=list)
    expect: DemoExpect

    @property
    def email(self) -> str:
        return f"{self.key}@{DEMO_EMAIL_DOMAIN}"


class DemoFile(BaseModel, extra="forbid"):
    accounts: list[DemoAccount]

    @model_validator(mode="after")
    def unique_keys(self) -> "DemoFile":
        keys = [a.key for a in self.accounts]
        if dupes := sorted({k for k in keys if keys.count(k) > 1}):
            raise ValueError(f"demo account keys used twice: {dupes}")
        return self


def read_demo_accounts(path: Path = DEMO_FILE) -> list[DemoAccount]:
    """The demo accounts in `path`, validated. Raises ValueError naming the problem."""
    try:
        return DemoFile.model_validate(json.loads(path.read_text(encoding="utf-8"))).accounts
    except (ValidationError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path.name}: {exc}") from exc


def load_demo_accounts(
    session: Session,
    password: str | None,
    path: Path = DEMO_FILE,
    notes: list[str] | None = None,
) -> list[DemoAccount]:
    """Create or rebuild every demo account in one transaction, after the content is loaded.
    Returns the accounts made: none if `password` is unset. Raises ValueError, writing nothing,
    if the file or the password is wrong, or an account doesn't reach its `expect`. Where an
    account's progress stopped short because the course doesn't allow more yet, a line saying so
    is added to `notes`."""
    if not password:
        return []
    accounts = read_demo_accounts(path)
    for account in accounts:
        if problem := password_problem(password, account.email, account.display_name):
            raise ValueError(f"DEMO_PASSWORD for {account.email}: {problem}")
    try:
        for account in accounts:
            stopped = _rebuild(session, account, hash_password(password))
            if notes is not None and stopped:
                notes.append(stopped)
    except Exception:
        session.rollback()
        raise
    session.commit()
    return accounts


def _rebuild(session: Session, account: DemoAccount, password_hash: str) -> str | None:
    user = session.scalar(select(User).where(User.email == account.email))
    if user is None:
        user = User(email=account.email)
        session.add(user)
    elif not user.is_demo:
        # Registering on the demo domain is refused, so this is an account made some other way.
        # Never take it over.
        raise ValueError(f"{account.email} exists and is not a demo account")
    user.display_name = account.display_name
    user.password_hash = password_hash
    user.is_staff = account.staff
    user.is_demo = True
    session.flush()

    delete_history(session, user.id)

    for n, step in enumerate(account.steps, start=1):
        for activity in _questions(session, step):
            where = f"{account.email}, step {n}, activity {activity.id}"
            while hint_level_seen(session, user.id, activity.id) < step.hints:
                if reveal_next_hint(session, user.id, activity) is None:
                    break  # fewer hints than asked for: show what there is
            record_attempt(session, user.id, activity, answer_for(activity, step.answer, where))
    stopped = _walk(session, user.id, account)

    outcomes = evaluate(session, user.id)
    ready = is_ready(outcomes)
    not_yet = sorted(o.objective.id for o in outcomes if o.state == "not_yet")
    if ready != account.expect.ready or not_yet != sorted(account.expect.not_yet):
        raise ValueError(
            f"{account.email}: expected ready={account.expect.ready}, not yet "
            f"{sorted(account.expect.not_yet)}, but the steps give ready={ready}, not yet {not_yet}"
        )
    return stopped


def _walk(session: Session, user_id: int, account: DemoAccount) -> str | None:
    """Move the account through its modules one segment at a time, through the module service, so
    the same rules apply as for a student. Returns why it stopped short, or None if it didn't."""
    for entry in account.progress:
        where = f"{account.email}, module {entry.module}"
        if session.get(Module, entry.module) is None:
            raise ValueError(f"{where}: no such module")
        count = len(
            session.scalars(select(Segment.id).where(Segment.module_id == entry.module)).all()
        )
        if count == 0:
            # No content yet: nothing to walk, and it doesn't lock the modules after it (FR-2.1).
            continue
        if entry.through == "end":
            last = count - 1
        elif entry.through >= count:
            raise ValueError(
                f"{where}: meant to stop partway, at segment {entry.through}, but the module has "
                f"only {count} segments"
            )
        else:
            last = entry.through - 1
        segments = session.scalars(
            select(Segment).where(Segment.module_id == entry.module).order_by(Segment.position)
        ).all()
        try:
            get_module_detail(session, user_id, entry.module)
            retrieval = session.scalars(
                select(Activity)
                .where(Activity.module_id == entry.module, Activity.purpose == "retrieval")
                .order_by(Activity.id)
            ).all()
            for activity in retrieval:
                submitted = answer_for(activity, "right", f"{where}, retrieval {activity.id}")
                record_attempt(session, user_id, activity, submitted)
            for position in range(last + 1):
                if position > 0:
                    _do(session, user_id, segments[position - 1], where)
                save_position(session, user_id, entry.module, position)
            if entry.through == "end":
                _do(session, user_id, segments[last], where)
                save_position(session, user_id, entry.module, last)  # "Finish module"
        except ModuleLocked:
            return (
                f"{account.email}: stopped at module {entry.module}, which is still locked "
                "because the module before it isn't complete"
            )
    return None


def _do(session: Session, user_id: int, segment: Segment, where: str) -> None:
    """Do the segment as a student would before moving past it (FR-2.7), if it isn't done yet:
    answer its activity, or pass every checkpoint of its video, right first time."""
    if segment.id in done_segments(session, user_id, [segment]):
        return
    if segment.kind == "activity":
        ids = [segment.activity_id]
    else:  # a video segment: its checkpoints not passed yet
        ids = list(
            session.scalars(
                select(Checkpoint.activity_id)
                .join(Video, Video.id == Checkpoint.video_id)
                .where(
                    Video.segment_id == segment.id,
                    Checkpoint.activity_id.not_in(
                        select(Attempt.activity_id).where(
                            Attempt.user_id == user_id, Attempt.correct.is_(True)
                        )
                    ),
                )
                .order_by(Checkpoint.at_seconds)
            )
        )
    for activity_id in ids:
        activity = session.get_one(Activity, activity_id)
        here = f"{where}, segment {segment.id}, activity {activity_id}"
        record_attempt(session, user_id, activity, answer_for(activity, "right", here))


def _questions(session: Session, step: DemoStep) -> list[Activity]:
    """The step's questions, in the order the module's segments show them."""
    shown = session.scalars(
        select(Activity)
        .join(Segment, Segment.activity_id == Activity.id)
        .where(Segment.module_id == step.module)
        .order_by(Segment.position)
    ).all()
    picked = [
        a
        for a in shown
        if (step.purposes is not None or a.purpose != "retrieval")
        and (step.purposes is None or a.purpose in step.purposes)
        and (step.objectives is None or a.objective_id in step.objectives)
        and a.objective_id not in step.except_objectives
    ]
    return picked[: step.limit]


def answer_for(activity: Activity, answer: Literal["right", "wrong"], where: str) -> dict[str, Any]:
    """A submission to `activity` that the checker marks right, or wrong, built from its stored
    solution. Checked with the real checker before it is used, so a kind whose answers this
    doesn't know how to build fails here, naming the activity, instead of seeding a wrong stage."""
    builders = _BUILDERS.get(activity.kind)
    if builders is None:
        raise ValueError(f"{where}: demo accounts can't answer a {activity.kind} activity yet")
    submission = builders[0 if answer == "right" else 1](activity)
    result = check_activity(activity.kind, activity.config, activity.solution, submission)
    if result.correct != (answer == "right"):
        raise ValueError(f"{where}: couldn't build a {answer} {activity.kind} answer")
    return submission


def _wrong_option(activity: Activity) -> dict[str, Any]:
    correct = MultipleChoiceSolution.model_validate(activity.solution).correct
    options = MultipleChoiceConfig.model_validate(activity.config).options
    return {"selected": next(o.id for o in options if o.id != correct)}


def _trace_rows(activity: Activity) -> dict[str, Any]:
    config = TraceConfig.model_validate(activity.config)
    scenario = GraphScenarioOut(id=0, name="", **config.model_dump())
    steps = run_bfs(scenario).steps
    return {
        "rows": [
            {
                "visitedVertex": s.visited_vertex,
                "queue": s.queue,
                "visited": s.visited,
                "order": s.order,
            }
            for s in steps
        ]
    }


def _wrong_pairs(activity: Activity) -> dict[str, Any]:
    """Every left item matched with a right item other than its own."""
    config = MatchingConfig.model_validate(activity.config)
    pairs = MatchingSolution.model_validate(activity.solution).pairs
    rights = [r.id for r in config.right]
    return {
        "pairs": {
            left.id: next((r for r in rights if r != pairs.get(left.id)), rights[0])
            for left in config.left
        }
    }


def _rotated_lines(activity: Activity) -> dict[str, Any]:
    """The solution's lines, each moved one place on: every line out of place."""
    order = list(ParsonsSolution.model_validate(activity.solution).order)
    return {"order": order[1:] + order[:1]}


def _wrong_tokens(activity: Activity) -> dict[str, Any]:
    """For every blank, a token it offers other than the right one."""
    config = FillInConfig.model_validate(activity.config)
    answers = FillInSolution.model_validate(activity.solution).answers
    return {
        "answers": {
            blank: next(o for o in config.options if o != answers.get(blank))
            for blank in config.blanks
        }
    }


def _harmless_tests(activity: Activity) -> dict[str, Any]:
    """The test cases that don't expose the bug (the seed refuses a set where every one does)."""
    exposing = set(ChooseTestsSolution.model_validate(activity.solution).exposing)
    tests = ChooseTestsConfig.model_validate(activity.config).tests
    return {"selected": [t.id for t in tests if t.id not in exposing]}


def _wrong_first_step(activity: Activity) -> dict[str, Any]:
    """One row that visits a vertex other than the start first."""
    config = TraceConfig.model_validate(activity.config)
    other = next(v for v in config.vertices if v != config.start_vertex)
    return {"rows": [{"visitedVertex": other, "queue": [], "visited": [other], "order": [other]}]}


# For each kind: how to build a right answer, and a wrong one. A wrong answer is one a student
# could send through the screens, made only of what the activity offers: the activity routes
# refuse an empty answer, or one naming anything else, with 422 (app/services/submissions.py), so
# every stage's results come from answers a real student could have given. It is the obvious
# mistake where there is one (a wrong option, leaving the bug in), and every part wrong otherwise.
Build = Callable[[Activity], dict[str, Any]]
_BUILDERS: dict[str, tuple[Build, Build]] = {
    "multiple_choice": (
        lambda a: {"selected": MultipleChoiceSolution.model_validate(a.solution).correct},
        _wrong_option,
    ),
    "matching": (
        lambda a: {"pairs": MatchingSolution.model_validate(a.solution).pairs},
        _wrong_pairs,
    ),
    "parsons": (
        lambda a: {"order": ParsonsSolution.model_validate(a.solution).order},
        _rotated_lines,
    ),
    "fill_in": (
        lambda a: {"answers": FillInSolution.model_validate(a.solution).answers},
        _wrong_tokens,
    ),
    "fix_the_bug": (
        lambda a: {"order": FixTheBugSolution.model_validate(a.solution).order},
        lambda a: {"order": [line.id for line in FixTheBugConfig.model_validate(a.config).lines]},
    ),
    "choose_tests": (
        lambda a: {"selected": ChooseTestsSolution.model_validate(a.solution).exposing},
        _harmless_tests,
    ),
    "trace": (_trace_rows, _wrong_first_step),
}
