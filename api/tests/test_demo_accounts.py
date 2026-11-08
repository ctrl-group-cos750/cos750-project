"""The seeded demo accounts (FR-1.4, app/seed/demo_accounts.py)."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, get_args

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Activity, Attempt, HintView, User
from app.schemas.activities import ActivityKind
from app.seed import FIXTURES, load
from app.seed.demo_accounts import (
    _BUILDERS,
    DemoStep,
    _questions,
    answer_for,
    load_demo_accounts,
    read_demo_accounts,
)
from app.services.checking import check_activity
from app.services.history import history_tables
from app.services.mastery import evaluate, is_ready

PASSWORD = "Demo pass 2026!"  # noqa: S105 (test only)
API_DIR = Path(__file__).resolve().parent.parent


def write(folder: Path, accounts: list[dict[str, Any]]) -> Path:
    path = folder / "accounts.json"
    path.write_text(json.dumps({"accounts": accounts}), encoding="utf-8")
    return path


def account(**overrides: Any) -> dict[str, Any]:
    return {
        "key": "mid",
        "display_name": "Demo: mid",
        "stage": "Halfway.",
        "expect": {"ready": False},
        **overrides,
    }


def report(db: Session, email: str) -> tuple[bool, list[int]]:
    """Whether the account is ready, and which objectives are "not yet"."""
    user = db.scalars(select(User).where(User.email == email)).one()
    outcomes = evaluate(db, user.id)
    return is_ready(outcomes), sorted(o.objective.id for o in outcomes if o.state == "not_yet")


def log_in(client: TestClient, email: str) -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200


# --- The committed accounts, against the committed content --------------------------------------


def test_the_committed_demo_accounts_are_the_four_stages() -> None:
    assert [a.key for a in read_demo_accounts()] == ["new", "mid", "not-yet", "ready"]


def test_each_committed_account_reaches_its_stage(db: Session) -> None:
    # The CI gate: a content change that stops an account meaning what it says fails here, in the
    # PR that made it, instead of on a deploy.
    load(db)
    load_demo_accounts(db, PASSWORD)
    assert report(db, "new@demo.example.com") == (False, [])
    assert report(db, "mid@demo.example.com") == (False, [])
    assert report(db, "not-yet@demo.example.com") == (False, [6])
    assert report(db, "ready@demo.example.com") == (True, [])


def test_the_not_yet_account_can_open_its_review_path_and_the_ready_one_cannot(
    db: Session, client: TestClient
) -> None:
    load(db)
    load_demo_accounts(db, PASSWORD)
    log_in(client, "not-yet@demo.example.com")
    assert client.get("/api/me/review/6").status_code == 200
    assert client.get("/api/me/report").json()["ready"] is False
    client.post("/api/auth/logout")
    log_in(client, "ready@demo.example.com")
    assert client.get("/api/me/review/6").status_code == 403
    assert client.get("/api/me/report").json()["ready"] is True


def test_the_mid_course_account_retried_with_hints(db: Session) -> None:
    load(db)
    load_demo_accounts(db, PASSWORD)
    user = db.scalars(select(User).where(User.email == "mid@demo.example.com")).one()
    first = _questions(db, DemoStep(module=3, limit=1, answer="right"))[0]
    tries = db.scalars(
        select(Attempt)
        .where(Attempt.user_id == user.id, Attempt.activity_id == first.id)
        .order_by(Attempt.id)
    ).all()
    assert [(a.correct, a.hint_level) for a in tries] == [(False, 0), (True, 2)]


def test_every_activity_kind_can_be_answered_right_and_wrong(db: Session) -> None:
    # A new kind without a builder would make every account that meets it fail, so CI says so
    # in the PR that adds the kind.
    assert set(_BUILDERS) == set(get_args(ActivityKind))
    load(db)
    for activity in db.scalars(select(Activity)):
        for want in ("right", "wrong"):
            built = answer_for(activity, want, f"activity {activity.id}")
            result = check_activity(activity.kind, activity.config, activity.solution, built)
            assert result.correct == (want == "right"), (activity.id, want)


def test_the_accounts_survive_content_that_changes_its_ids(tmp_path: Path) -> None:
    # What #28 will do: module 6's placeholders replaced by items with other ids. Accounts name
    # questions by module, purpose and objective, never by id, so they still reach their stages.
    for f in FIXTURES.glob("*.json"):
        shutil.copy(f, tmp_path)
    module_6 = json.loads((tmp_path / "module-6.json").read_text())
    new_id = {a["id"]: a["id"] + 90 for a in module_6["activities"]}
    for a in module_6["activities"]:
        a["id"] = new_id[a["id"]]
    for m in module_6["modules"]:
        for seg in m["segments"]:
            if seg.get("activity_id") in new_id:
                seg["activity_id"] = new_id[seg["activity_id"]]
    (tmp_path / "module-6.json").write_text(json.dumps(module_6))

    fresh = create_engine("sqlite://")
    Base.metadata.create_all(fresh)
    with Session(fresh) as session:
        load(session, tmp_path)
        load_demo_accounts(session, PASSWORD)
        assert report(session, "not-yet@demo.example.com") == (False, [6])
        assert report(session, "ready@demo.example.com") == (True, [])


# --- Rules -------------------------------------------------------------------------------------


def test_no_password_means_no_demo_accounts(db: Session) -> None:
    assert load_demo_accounts(db, None) == []
    assert load_demo_accounts(db, "") == []
    assert db.scalars(select(User)).all() == []


def test_a_weak_password_is_refused(tmp_path: Path, db: Session) -> None:
    with pytest.raises(ValueError, match="DEMO_PASSWORD"):
        load_demo_accounts(db, "password", write(tmp_path, [account()]))
    assert db.scalars(select(User)).all() == []


@pytest.mark.parametrize(
    ("accounts", "problem"),
    [
        ([account(), account()], "used twice"),
        ([account(key="Not A Key")], "pattern"),
        ([account(extra="x")], "extra"),
        ([{k: v for k, v in account().items() if k != "expect"}], "expect"),
        ([account(steps=[{"module": 3, "answer": "maybe"}])], "answer"),
        ([account(steps=[{"module": 3, "answer": "right", "hints": 5}])], "hints"),
        ([account(steps=[{"activity": 301, "answer": "right"}])], "module"),
    ],
)
def test_invalid_demo_files_are_refused(
    tmp_path: Path, accounts: list[dict[str, Any]], problem: str
) -> None:
    with pytest.raises(ValueError, match=problem):
        read_demo_accounts(write(tmp_path, accounts))


def test_an_account_that_misses_its_expected_stage_writes_nothing(
    tmp_path: Path, db: Session
) -> None:
    load(db)
    wrong = account(key="b", steps=[{"module": 6, "answer": "wrong"}], expect={"ready": True})
    with pytest.raises(ValueError, match=r"b@demo\.example\.com: expected ready=True"):
        load_demo_accounts(db, PASSWORD, write(tmp_path, [account(), wrong]))
    assert db.scalars(select(User)).all() == []


def test_a_rerun_rebuilds_the_account_and_leaves_students_alone(
    tmp_path: Path, db: Session
) -> None:
    load(db)
    path = write(tmp_path, [account(steps=[{"module": 3, "limit": 1, "answer": "right"}])])
    load_demo_accounts(db, PASSWORD, path)
    demo = db.scalars(select(User).where(User.is_demo)).one()
    question = _questions(db, DemoStep(module=3, limit=1, answer="right"))[0]
    student = User(email="ada@example.com", display_name="Ada", password_hash="x")  # noqa: S106
    db.add(student)
    db.flush()
    # A rehearsal clicks around in the demo account, and a real student answers too.
    for user_id in (demo.id, student.id):
        db.add(
            Attempt(
                user_id=user_id,
                activity_id=question.id,
                submitted={},
                correct=False,
                score=0,
                detail={},
            )
        )
        db.add(HintView(user_id=user_id, activity_id=question.id, level=1))
    db.commit()

    load_demo_accounts(db, PASSWORD, path)
    by_user = sorted(a.user_id for a in db.scalars(select(Attempt)))
    assert by_user == sorted([demo.id, student.id])  # the demo's one seeded, and the student's
    assert [v.user_id for v in db.scalars(select(HintView))] == [student.id]
    assert db.scalars(select(User).where(User.is_demo)).one().id == demo.id  # same row, same id


def test_an_existing_real_account_is_never_taken_over(tmp_path: Path, db: Session) -> None:
    db.add(User(email="mid@demo.example.com", display_name="Someone", password_hash="x"))  # noqa: S106
    db.commit()
    with pytest.raises(ValueError, match="not a demo account"):
        load_demo_accounts(db, PASSWORD, write(tmp_path, [account()]))
    assert db.scalars(select(User)).one().display_name == "Someone"


def test_the_reset_covers_every_table_of_student_history() -> None:
    # A new table of student history must point at users with `user_id`, or a reset will leave
    # rehearsal clicks in it. Update this list when you add one.
    assert sorted(t.name for t, _ in history_tables()) == [
        "attempts",
        "hint_views",
        "objective_results",
        "points_entries",
        "user_badges",
    ]


def test_a_demo_account_can_log_in(tmp_path: Path, db: Session, client: TestClient) -> None:
    load_demo_accounts(db, PASSWORD, write(tmp_path, [account(staff=True)]))
    response = client.post(
        "/api/auth/login", json={"email": "mid@demo.example.com", "password": PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["isStaff"] is True


def test_nobody_can_register_on_the_demo_domain(db: Session, client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": "Mid@Demo.Example.com", "displayName": "Mallory", "password": PASSWORD},
    )
    assert response.status_code == 409
    assert db.scalars(select(User)).all() == []


# --- The seed command ---------------------------------------------------------------------------


def test_a_demo_account_problem_never_stops_the_seed(tmp_path: Path) -> None:
    # The API only starts once `python -m app.seed` succeeds (Dockerfile), so a demo problem, here
    # a weak DEMO_PASSWORD, must be reported without failing it.
    url = f"sqlite:///{tmp_path / 'seed.db'}"
    Base.metadata.create_all(create_engine(url))
    env = {**os.environ, "DATABASE_URL": url, "DEMO_PASSWORD": "weak"}
    run = subprocess.run(
        [sys.executable, "-m", "app.seed"],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    assert "demo accounts NOT rebuilt" in run.stdout
    assert "DEMO_PASSWORD" in run.stdout
