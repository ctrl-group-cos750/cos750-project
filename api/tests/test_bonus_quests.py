"""Optional bonus quests (FR-8.3, FR-9.3; #87): extra challenge that never holds a student back,
earns its own points and badge, and never touches mastery."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Module, ModuleProgress, ObjectiveResult, PointsEntry, Segment
from app.routers.activities import QUEST_CLOSED
from app.seed import load

STUDENT = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}
RIGHT = {"submitted": {"selected": "a"}}
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


def reach(
    db: Session, user_id: int, module: int, position: int, status: str = "in_progress"
) -> None:
    """The student's furthest segment in `module` (0-based), as the module page saves it."""
    row = db.scalar(
        select(ModuleProgress).where(
            ModuleProgress.user_id == user_id, ModuleProgress.module_id == module
        )
    )
    if row is None:
        row = ModuleProgress(user_id=user_id, module_id=module)
        db.add(row)
    row.status, row.current_segment_position = status, position
    db.commit()


def quest_index(db: Session, module: int, quest: int) -> int:
    segments = db.scalars(
        select(Segment).where(Segment.module_id == module).order_by(Segment.position)
    ).all()
    return next(i for i, s in enumerate(segments) if s.activity_id == quest)


def test_a_bonus_quest_opens_where_its_module_offers_it(client: TestClient, db: Session) -> None:
    """The quest is the module's last segment, reached before the module is complete: it opens
    there, not only once the module is finished, or the module would offer a shut quest (#224
    review). Before then it is shut, so it can't be done ahead of the module."""
    load(db)
    user_id = log_in(client)
    open_through(db, user_id, 3)
    index = quest_index(db, 3, 380)
    assert index == len(client.get("/api/modules/3").json()["segments"]) - 1  # the last one

    response = client.get("/api/activities/380")
    assert (response.status_code, response.json()["detail"]) == (403, QUEST_CLOSED)
    reach(db, user_id, 3, index - 1)
    assert client.get("/api/activities/380").status_code == 403
    assert client.post("/api/activities/380/attempts", json=RIGHT).status_code == 403

    reach(db, user_id, 3, index)  # at its segment, the module not finished yet
    assert client.get("/api/activities/380").status_code == 200
    answer(client, 380, "a")
    assert badges(client) == [("quest", "380")]


def test_a_bonus_quest_stays_open_once_its_module_is_finished(
    client: TestClient, db: Session
) -> None:
    """Finished, and restarted (which starts the module again at its first segment, but keeps it
    complete): the quest stays open."""
    load(db)
    user_id = log_in(client)
    open_through(db, user_id, 4)  # module 3 complete
    reach(db, user_id, 3, 0, status="complete")
    assert client.get("/api/activities/380").status_code == 200
    assert client.get("/api/activities/480").status_code == 403  # module 4 not reached


def test_the_offer_lists_open_quests_in_module_order(client: TestClient, db: Session) -> None:
    load(db)
    user_id = log_in(client)
    assert client.get("/api/quests").json() == []
    open_through(db, user_id, 5)  # modules 3 and 4 complete
    offer = client.get("/api/quests").json()
    assert [(q["id"], q["moduleId"], q["moduleNumber"], q["completed"]) for q in offer] == [
        (380, 3, 3, False),
        (480, 4, 4, False),
    ]
    assert offer[0]["title"]
    assert offer[0]["moduleTitle"]
    answer(client, 480, "b")  # wrong: the offer stays, not completed
    answer(client, 380, "a")
    assert [(q["id"], q["completed"]) for q in client.get("/api/quests").json()] == [
        (380, True),
        (480, False),
    ]


def test_the_offer_needs_a_login_and_is_the_students_own(client: TestClient, db: Session) -> None:
    load(db)
    assert client.get("/api/quests").status_code == 401
    user_id = log_in(client)
    open_through(db, user_id, 4)
    answer(client, 380, "a")
    client.post("/api/auth/logout")
    other = {"email": "bob@example.com", "password": "Correct horse 2", "displayName": "Bob"}
    assert client.post("/api/auth/register", json=other).status_code == 201
    assert client.get("/api/quests").json() == []  # Bob has finished nothing


def test_a_right_answer_earns_the_quest_and_both_earn_all_quests(
    client: TestClient, db: Session
) -> None:
    load(db)
    open_through(db, log_in(client), 5)

    answer(client, 380, "a")
    # The quest's 20 points, and no activity points on top of them. The badge's ref is the
    # quest's activity id; the shelf numbers quests for display (#196 review).
    assert client.get("/api/rewards").json()["points"] == 20
    assert badges(client) == [("quest", "380")]

    answer(client, 480, "a")
    assert client.get("/api/rewards").json()["points"] == 40
    assert sorted(badges(client)) == [("all-quests", ""), ("quest", "380"), ("quest", "480")]

    answer(client, 480, "a")  # once: a repeat earns nothing more
    assert client.get("/api/rewards").json()["points"] == 40


def test_wrong_then_right_earns_nothing_and_no_quest_touches_mastery(
    client: TestClient, db: Session
) -> None:
    """Only a first attempt counts (the evidence rule, FR-9.6): wrong then right on a quest pays
    no points and no Quest badge, and so All Quests can't come either (review of 13 Nov on #221:
    it paid 20 points and both badges)."""
    load(db)
    user_id = log_in(client)
    open_through(db, user_id, 5)
    answer(client, 380, "b")
    assert client.get("/api/rewards").json()["points"] == 0
    answer(client, 380, "a")
    assert client.get("/api/rewards").json()["points"] == 0
    assert badges(client) == []
    answer(client, 480, "a")
    assert db.scalars(select(ObjectiveResult).where(ObjectiveResult.user_id == user_id)).all() == []
    refs = db.scalars(select(PointsEntry.ref).where(PointsEntry.user_id == user_id)).all()
    assert sorted(refs) == ["quest:480"]
    assert badges(client) == [("quest", "480")]  # not All Quests: 380 wasn't earned


def test_a_quest_answered_after_the_hints_give_it_away_earns_nothing(
    client: TestClient, db: Session
) -> None:
    """Hints 3 and 4 give the answer away, so a quest answered after them earns no points or
    badge (badges mark real progress), and the hint before them warns that it will (#196)."""
    load(db)
    open_through(db, log_in(client), 5)
    shown = [client.post("/api/activities/480/hints").json() for _ in range(4)]
    assert [h["nextCountsAsSupport"] for h in shown] == [False, True, True, False]
    assert shown[-1]["body"] == "Answer: F."
    answer(client, 480, "a")
    assert client.get("/api/rewards").json()["points"] == 0
    assert badges(client) == []


def test_a_clean_right_answer_earns_20_points_and_the_badge_once(
    client: TestClient, db: Session
) -> None:
    load(db)
    open_through(db, log_in(client), 5)
    assert client.post("/api/activities/480/hints").status_code == 201  # hint 1 still counts
    answer(client, 480, "a")
    answer(client, 480, "a")
    assert client.get("/api/rewards").json()["points"] == 20
    assert badges(client) == [("quest", "480")]


def test_all_quests_counts_only_quests_a_student_can_reach(client: TestClient, db: Session) -> None:
    """A hidden or unplaced bonus activity would make All Quests impossible, so it isn't counted."""
    load(db)
    open_through(db, log_in(client), 5)
    hidden = db.get_one(Activity, 380)
    db.add(
        Activity(
            id=990,
            kind=hidden.kind,
            title="An unplaced bonus quest",
            visible=True,
            config=hidden.config,
            solution=hidden.solution,
            module_id=3,
            purpose="bonus",
        )
    )
    hidden.visible = False
    db.commit()
    assert db.scalars(select(Segment).where(Segment.activity_id == 990)).all() == []

    answer(client, 480, "a")
    assert sorted(badges(client)) == [("all-quests", ""), ("quest", "480")]
