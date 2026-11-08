"""Seeded demo accounts at different points in the course (SE document FR-1.4), so the demo and the
end-to-end tests can show any stage without working through 75 minutes of content.

Each account is in demo/accounts.json: who it is, the steps that put it at its stage, and what that
stage must look like. A step names questions by where they are, never by id: "answer module 6's
mastery items right, except objective 6's". The seed finds those questions in the order a student
meets them, builds a right or wrong answer from each one's stored solution, and submits it through
the same code a student's answers go through (app/services/attempts.py). So new or replaced content
never breaks an account, and every result is the one the real mastery rules work out.

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
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Activity, Segment, User
from app.models.user import DEMO_EMAIL_DOMAIN
from app.passwords import password_problem
from app.schemas.activities import (
    ChooseTestsSolution,
    FillInSolution,
    FixTheBugConfig,
    FixTheBugSolution,
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
from app.services.modules import ModuleLocked, ModuleNotFound, PositionTooFar, save_position

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


class DemoExpect(BaseModel, extra="forbid"):
    """What the account's mastery report must say once its steps are done (FR-7.3, FR-7.4)."""

    ready: bool
    not_yet: list[int] = Field(default_factory=list)  # exactly these objectives are "not yet"


class DemoPlace(BaseModel, extra="forbid"):
    """How far into a module the account has got: `segment` is 0-based."""

    module: int
    segment: int = Field(ge=0)


class DemoAccount(BaseModel, extra="forbid"):
    # The email's local part: "new" is new@demo.example.com.
    key: str = Field(pattern=r"^[a-z][a-z0-9-]{0,30}$")
    display_name: str = Field(min_length=1, max_length=50)
    # Where in the course this account is, for whoever runs the demo.
    stage: str = Field(min_length=1)
    staff: bool = False
    steps: list[DemoStep] = Field(default_factory=list)
    # The modules it has worked through, in order, and where it is now (FR-2.5, FR-2.6). A module
    # with no segments yet is passed over, as it is for a student.
    modules_done: list[int] = Field(default_factory=list)
    reached: DemoPlace | None = None
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
    session: Session, password: str | None, path: Path = DEMO_FILE
) -> list[DemoAccount]:
    """Create or rebuild every demo account in one transaction, after the content is loaded.
    Returns the accounts made: none if `password` is unset. Raises ValueError, writing nothing,
    if the file or the password is wrong, or an account doesn't reach its `expect`."""
    if not password:
        return []
    accounts = read_demo_accounts(path)
    for account in accounts:
        if problem := password_problem(password, account.email, account.display_name):
            raise ValueError(f"DEMO_PASSWORD for {account.email}: {problem}")
    try:
        for account in accounts:
            _rebuild(session, account, hash_password(password))
    except Exception:
        session.rollback()
        raise
    session.commit()
    return accounts


def _rebuild(session: Session, account: DemoAccount, password_hash: str) -> None:
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

    _walk_modules(session, user.id, account)

    outcomes = evaluate(session, user.id)
    ready = is_ready(outcomes)
    not_yet = sorted(o.objective.id for o in outcomes if o.state == "not_yet")
    if ready != account.expect.ready or not_yet != sorted(account.expect.not_yet):
        raise ValueError(
            f"{account.email}: expected ready={account.expect.ready}, not yet "
            f"{sorted(account.expect.not_yet)}, but the steps give ready={ready}, not yet {not_yet}"
        )


def _walk_modules(session: Session, user_id: int, account: DemoAccount) -> None:
    """Move through the account's modules one segment at a time, through the same code the module
    page uses (app/services/modules.py), so the map shows what a student would see."""
    walks: list[tuple[int, int | None]] = [(m, None) for m in account.modules_done]
    if account.reached is not None:
        walks.append((account.reached.module, account.reached.segment))
    for module_id, stop in walks:
        segments = session.scalar(
            select(func.count()).select_from(Segment).where(Segment.module_id == module_id)
        )
        last = (segments or 0) - 1 if stop is None else stop
        try:
            for position in range(last + 1):
                save_position(session, user_id, module_id, position)
        except (ModuleNotFound, ModuleLocked, PositionTooFar) as exc:
            raise ValueError(
                f"{account.email}: can't reach segment {last} of module {module_id} "
                f"({type(exc).__name__})"
            ) from exc


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
        if (step.purposes is None or a.purpose in step.purposes)
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


# For each kind: how to build a right answer, and a wrong one. A wrong answer is the mistake a
# student would make where there is an obvious one (a wrong option, leaving the bug in), and an
# empty answer otherwise.
Build = Callable[[Activity], dict[str, Any]]
_BUILDERS: dict[str, tuple[Build, Build]] = {
    "multiple_choice": (
        lambda a: {"selected": MultipleChoiceSolution.model_validate(a.solution).correct},
        _wrong_option,
    ),
    "matching": (
        lambda a: {"pairs": MatchingSolution.model_validate(a.solution).pairs},
        lambda a: {"pairs": {}},
    ),
    "parsons": (
        lambda a: {"order": ParsonsSolution.model_validate(a.solution).order},
        lambda a: {"order": []},
    ),
    "fill_in": (
        lambda a: {"answers": FillInSolution.model_validate(a.solution).answers},
        lambda a: {"answers": {}},
    ),
    "fix_the_bug": (
        lambda a: {"order": FixTheBugSolution.model_validate(a.solution).order},
        lambda a: {"order": [line.id for line in FixTheBugConfig.model_validate(a.config).lines]},
    ),
    "choose_tests": (
        lambda a: {"selected": ChooseTestsSolution.model_validate(a.solution).exposing},
        lambda a: {"selected": []},
    ),
    "trace": (_trace_rows, lambda a: {"rows": []}),
}
