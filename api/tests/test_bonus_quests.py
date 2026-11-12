"""Optional bonus quests (FR-8.3, FR-9.3; #87): extra challenge that never holds a student back,
earns its own points and badge, and never touches mastery."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Module, ModuleProgress, ObjectiveResult, PointsEntry
from app.seed import load

STUDENT = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}
QUESTS = (380, 480)  # module 3's and module 4's, in the course's order


def log_in(client: TestClient) -> int:
    assert client.post("/api/auth/register", json=STUDENT).status_code == 201
    return int(client.get("/api/auth/me").json()["id"])


def open_through(db: Session, user_id: int, module: int) -> None:
    """Mark every module before `module` complete, which opens it."""
    for m in db.scalars(select(Module).where(Module.position < module)):
        db.add(ModuleProgress(user_id=user_id, module_id=m.id, status="complete"))
    db.commit()


def answer(client: TestClient, activity: int, option: str) -> None:
    res = client.post(
        f"/api/activities/{activity}/attempts", json={"submitted": {"selected": option}}
    )
    assert res.status_code == 201, res.text


def badges(client: TestClient) -> list[tuple[str, str]]:
    return [(b["badge"], b["ref"]) for b in client.get("/api/rewards").json()["badges"]]


def test_a_bonus_quest_is_optional_and_never_holds_next_back(
    client: TestClient, db: Session
) -> None:
    load(db)
    open_through(db, log_in(client), 3)
    segment = next(s for s in client.get("/api/modules/3").json()["segments"] if s["id"] == 380)
    assert (segment["optional"], segment["done"], segment["attempted"]) == (True, True, False)


def test_a_right_answer_earns_the_quest_and_both_earn_all_quests(
    client: TestClient, db: Session
) -> None:
    load(db)
    open_through(db, log_in(client), 5)

    answer(client, 380, "a")
    # The quest's 20 points, and no activity points on top of them.
    assert client.get("/api/rewards").json()["points"] == 20
    assert badges(client) == [("quest", "1")]

    answer(client, 480, "a")
    assert client.get("/api/rewards").json()["points"] == 40
    assert sorted(badges(client)) == [("all-quests", ""), ("quest", "1"), ("quest", "2")]


def test_a_wrong_answer_earns_nothing_and_no_quest_touches_mastery(
    client: TestClient, db: Session
) -> None:
    load(db)
    user_id = log_in(client)
    open_through(db, user_id, 5)
    answer(client, 380, "b")
    assert client.get("/api/rewards").json()["points"] == 0
    answer(client, 380, "a")
    answer(client, 480, "a")
    assert db.scalars(select(ObjectiveResult).where(ObjectiveResult.user_id == user_id)).all() == []
    refs = db.scalars(select(PointsEntry.ref).where(PointsEntry.user_id == user_id)).all()
    assert sorted(refs) == ["quest:1", "quest:2"]
