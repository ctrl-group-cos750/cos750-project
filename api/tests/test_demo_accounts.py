"""The seeded demo accounts (FR-1.4, app/seed/demo_accounts.py)."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attempt, HintView, User
from app.seed import load
from app.seed.demo_accounts import _history_tables, load_demo_accounts, read_demo_accounts

PASSWORD = "Demo pass 2026!"  # noqa: S105 (test only)


def write(folder: Path, accounts: list[dict[str, Any]]) -> Path:
    path = folder / "accounts.json"
    path.write_text(json.dumps({"accounts": accounts}), encoding="utf-8")
    return path


def account(**overrides: Any) -> dict[str, Any]:
    return {"key": "mid", "display_name": "Demo: mid", "stage": "Halfway.", **overrides}


def content(folder: Path) -> Path:
    """One multiple-choice activity (id 1, answer "a") with two hints."""
    (folder / "content.json").write_text(
        json.dumps(
            {
                "activities": [
                    {
                        "id": 1,
                        "kind": "multiple_choice",
                        "title": "Q",
                        "config": {
                            "prompt": "Q",
                            "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                        },
                        "solution": {"correct": "a"},
                        "hints": [{"level": 1, "body": "one"}, {"level": 2, "body": "two"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return folder


def test_the_committed_demo_accounts_are_valid() -> None:
    assert [a.key for a in read_demo_accounts()] == ["new"]


def test_the_committed_demo_accounts_load_against_the_committed_content(db: Session) -> None:
    load(db)
    made = load_demo_accounts(db, PASSWORD)
    assert {a.email for a in made} == {"new@demo.example.com"}


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
        ([account(attempts=[{"activity": 1, "submitted": {}}])], "correct"),
        (
            [
                account(
                    attempts=[{"activity": 1, "submitted": {}, "correct": True, "hints_seen": 5}]
                )
            ],
            "hints_seen",
        ),
    ],
)
def test_invalid_demo_files_are_refused(
    tmp_path: Path, accounts: list[dict[str, Any]], problem: str
) -> None:
    with pytest.raises(ValueError, match=problem):
        read_demo_accounts(write(tmp_path, accounts))


def test_history_is_replayed_through_the_real_checker_and_hints(
    tmp_path: Path, db: Session
) -> None:
    load(db, content(tmp_path))
    steps = [
        {"activity": 1, "submitted": {"selected": "b"}, "correct": False},
        {"activity": 1, "hints_seen": 2, "submitted": {"selected": "a"}, "correct": True},
    ]
    load_demo_accounts(db, PASSWORD, write(tmp_path, [account(attempts=steps)]))

    user = db.scalars(select(User).where(User.email == "mid@demo.example.com")).one()
    assert user.is_demo
    assert not user.is_staff
    attempts = db.scalars(select(Attempt).where(Attempt.user_id == user.id).order_by(Attempt.id))
    assert [(a.correct, a.hint_level) for a in attempts] == [(False, 0), (True, 2)]
    assert len(db.scalars(select(HintView)).all()) == 2


@pytest.mark.parametrize(
    ("step", "problem"),
    [
        ({"activity": 99, "submitted": {"selected": "a"}, "correct": True}, "no activity 99"),
        ({"activity": 1, "submitted": {"selected": "b"}, "correct": True}, "meant to be right"),
        ({"activity": 1, "submitted": {"order": []}, "correct": True}, "shape"),
        (
            {"activity": 1, "hints_seen": 3, "submitted": {"selected": "a"}, "correct": True},
            "no hint 3",
        ),
    ],
)
def test_a_history_that_does_not_fit_the_content_writes_nothing(
    tmp_path: Path, db: Session, step: dict[str, Any], problem: str
) -> None:
    load(db, content(tmp_path))
    with pytest.raises(ValueError, match=problem):
        load_demo_accounts(
            db, PASSWORD, write(tmp_path, [account(), account(key="b", attempts=[step])])
        )
    assert db.scalars(select(User)).all() == []


def test_a_rerun_rebuilds_the_account_and_leaves_students_alone(
    tmp_path: Path, db: Session
) -> None:
    load(db, content(tmp_path))
    path = write(
        tmp_path,
        [account(attempts=[{"activity": 1, "submitted": {"selected": "a"}, "correct": True}])],
    )
    load_demo_accounts(db, PASSWORD, path)
    demo = db.scalars(select(User).where(User.is_demo)).one()
    student = User(email="ada@example.com", display_name="Ada", password_hash="x")  # noqa: S106
    db.add(student)
    db.flush()
    # A rehearsal clicks around in the demo account, and a real student answers too.
    for user_id in (demo.id, student.id):
        db.add(
            Attempt(user_id=user_id, activity_id=1, submitted={}, correct=False, score=0, detail={})
        )
    db.commit()

    load_demo_accounts(db, PASSWORD, path)
    by_user = [a.user_id for a in db.scalars(select(Attempt))]
    assert sorted(by_user) == sorted([demo.id, student.id])  # the demo's one seeded, the student's
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
    assert sorted(t.name for t, _ in _history_tables()) == ["attempts", "hint_views"]


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
