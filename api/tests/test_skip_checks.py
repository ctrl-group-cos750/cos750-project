"""Skipping a refresher by passing its short check (FR-8.1, FR-8.2; #224): module 0's diagnostic
questions are the checks for the refreshers after them. Read from attempts on the real content."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_demo_accounts import PASSWORD, account, write

from app.models import HintView, ModuleProgress, User
from app.seed import load
from app.seed.demo_accounts import load_demo_accounts

STUDENT = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}


def log_in(client: TestClient) -> int:
    assert client.post("/api/auth/register", json=STUDENT).status_code == 201
    return int(client.get("/api/auth/me").json()["id"])


def answer(client: TestClient, activity: int, option: str) -> None:
    res = client.post(
        f"/api/activities/{activity}/attempts", json={"submitted": {"selected": option}}
    )
    assert res.status_code == 201, res.text


def refreshers(client: TestClient) -> dict[int, tuple[int | None, str | None, bool]]:
    """Each refresher of module 0, by its check: (index, its skip check state, shown)."""
    segments = client.get("/api/modules/0").json()["segments"]
    return {
        s["skipCheckActivityId"]: (i, s["skipCheck"], s["shown"])
        for i, s in enumerate(segments)
        if s["kind"] == "refresher"
    }


def test_a_right_first_answer_skips_the_refresher_after_it(client: TestClient, db: Session) -> None:
    load(db)
    log_in(client)
    assert {c: (state, shown) for c, (_, state, shown) in refreshers(client).items()} == {
        1: ("not_taken", True),
        2: ("not_taken", True),
        3: ("not_taken", True),
    }
    answer(client, 1, "a")  # right
    state = {c: (s, shown) for c, (_, s, shown) in refreshers(client).items()}
    assert state[1] == ("passed", False)  # skipped: kept in place, done, not shown
    assert state[2] == ("not_taken", True)
    detail = client.get("/api/modules/0").json()
    index = refreshers(client)[1][0]
    assert detail["segments"][index]["done"] is True
    assert len(detail["segments"]) == 8  # positions never shift


def test_only_a_clean_first_answer_passes(client: TestClient, db: Session) -> None:
    """Wrong first: the refresher stays, even after a right second answer. Right after hint 3:
    the hint gave it away, so it stays too."""
    load(db)
    user_id = log_in(client)
    answer(client, 1, "b")
    answer(client, 1, "a")
    for level in (1, 2, 3):
        db.add(HintView(user_id=user_id, activity_id=2, level=level))
    db.commit()
    attempt = client.post("/api/activities/2/attempts", json={"submitted": {"selected": "a"}})
    assert attempt.json()["correct"] is True
    state = {c: (s, shown) for c, (_, s, shown) in refreshers(client).items()}
    assert state[1] == ("not_passed", True)
    assert state[2] == ("not_passed", True)
    assert state[3] == ("not_taken", True)


def test_a_demo_walk_moves_past_a_refresher_its_answer_skipped(tmp_path: Path, db: Session) -> None:
    """The walk answers each diagnostic, which can hide the refresher after it, so the next
    segment is worked out after the answer, as the page does (#224): module 0 ends complete."""
    load(db)
    path = write(tmp_path, [account(progress=[{"module": 0}], expect={"ready": False})])
    load_demo_accounts(db, PASSWORD, path)
    user = db.scalars(select(User).where(User.email == "mid@demo.example.com")).one()
    row = db.scalars(
        select(ModuleProgress).where(
            ModuleProgress.user_id == user.id, ModuleProgress.module_id == 0
        )
    ).one()
    assert row.status == "complete"
