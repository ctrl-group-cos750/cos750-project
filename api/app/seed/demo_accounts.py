"""Seeded demo accounts at different points in the course (SE document FR-1.4), so the demo and the
end-to-end tests can show any stage without working through 75 minutes of content.

Each account is in demo/accounts.json: who it is, and the history that puts it at its stage, as the
attempts it made and the hints it saw before each. `python -m app.seed` rebuilds them every time it
runs (the API container does on every start): each demo account's rows are deleted and its history
is replayed through the same code a student's answers go through (app/services/attempts.py). So a
rehearsal that clicked through an account is undone by the next seed, and a progress or mastery
figure is always the one the real code works out, never one written by hand.

Every demo account shares one password, from DEMO_PASSWORD in the server's environment (Coolify).
It is never committed. Unset, no demo accounts are made: an environment only has them on purpose.
"""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, User
from app.models.user import DEMO_EMAIL_DOMAIN
from app.passwords import password_problem
from app.security import hash_password
from app.services.attempts import hint_level_seen, record_attempt, reveal_next_hint
from app.services.history import delete_history

DEMO_FILE = Path(__file__).parent / "demo" / "accounts.json"


class DemoAttempt(BaseModel, extra="forbid"):
    activity: int
    # The hint level the account has seen on this activity before submitting: hints up to it are
    # revealed first. 3 or 4 makes a correct answer "met with support" (FR-7.2).
    hints_seen: int = Field(default=0, ge=0, le=4)
    # In the kind's shape, as the browser sends it: {"selected": ...}, {"order": [...]}, ...
    submitted: dict[str, Any]
    # What the author means this attempt to be. The load fails if the checker disagrees, so a
    # content change that quietly turns a demo's wrong answer right (or back) is caught.
    correct: bool


class DemoAccount(BaseModel, extra="forbid"):
    # The email's local part: "new" is new@demo.example.com.
    key: str = Field(pattern=r"^[a-z][a-z0-9-]{0,30}$")
    display_name: str = Field(min_length=1, max_length=50)
    # Where in the course this account is, for whoever runs the demo.
    stage: str = Field(min_length=1)
    staff: bool = False
    attempts: list[DemoAttempt] = Field(default_factory=list)

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
    if the file, the password or an account's history is wrong."""
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

    for n, step in enumerate(account.attempts, start=1):
        where = f"{account.email}, attempt {n}"
        activity = session.get(Activity, step.activity)
        if activity is None:
            raise ValueError(f"{where}: no activity {step.activity}")
        while hint_level_seen(session, user.id, activity.id) < step.hints_seen:
            if reveal_next_hint(session, user.id, activity) is None:
                raise ValueError(f"{where}: activity {activity.id} has no hint {step.hints_seen}")
        try:
            _, result = record_attempt(session, user.id, activity, step.submitted)
        except ValidationError as exc:
            raise ValueError(f"{where}: submission not in the {activity.kind} shape") from exc
        if result.correct != step.correct:
            raise ValueError(
                f"{where}: meant to be {'right' if step.correct else 'wrong'}, "
                f"but the checker says {result.feedback!r}"
            )
