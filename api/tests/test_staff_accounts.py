"""The staff portal's "Accounts" pages (GET/DELETE /api/staff/accounts): every account, one
account's progress, and deleting an account with everything stored about it."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Activity,
    Attempt,
    Checkpoint,
    Hint,
    HintView,
    PointsEntry,
    User,
    UserBadge,
    Video,
)
from app.routers.staff_accounts import mask_email
from app.services import rewards
from app.services.pseudonym import pseudonym

PASSWORD = "Correct horse 1"  # noqa: S105 (a test account)


def make_video(db: Session) -> tuple[int, int, int]:
    """A video with two multiple-choice checkpoints, "early" (correct: a, one hint) and "late"."""

    def choice(title: str) -> Activity:
        options = [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]
        return Activity(
            kind="multiple_choice",
            title=title,
            visible=True,
            config={"prompt": title, "options": options},
            solution={"correct": "a", "feedback": {}},
        )

    early, late = choice("early"), choice("late")
    video = Video(
        title="Meet BFS",
        media_path="/media/videos/meet-bfs.mp4",
        captions_path="/media/videos/meet-bfs.vtt",
        transcript="Words",
        duration_seconds=60,
    )
    db.add_all([early, late, video])
    db.flush()
    db.add_all(
        [
            Checkpoint(video_id=video.id, at_seconds=20, activity_id=early.id),
            Checkpoint(video_id=video.id, at_seconds=45, activity_id=late.id),
            Hint(activity_id=early.id, level=1, body="FIFO"),
        ]
    )
    db.commit()
    return video.id, early.id, late.id


def register(client: TestClient, email: str, name: str) -> int:
    body = {"email": email, "password": PASSWORD, "displayName": name}
    response = client.post("/api/auth/register", json=body)
    assert response.status_code == 201
    return int(response.json()["id"])


def log_in(client: TestClient, email: str) -> None:
    client.cookies.clear()
    body = {"email": email, "password": PASSWORD}
    assert client.post("/api/auth/login", json=body).status_code == 200


def make_staff(db: Session, user_id: int) -> None:
    user = db.get(User, user_id)
    assert user is not None
    user.is_staff = True
    db.commit()


def ada_does_some_work(client: TestClient, db: Session) -> tuple[int, int]:
    """Ada answers the early checkpoint wrong, takes a hint, then answers it right."""
    video_id, early, _ = make_video(db)
    ada = register(client, "ada@example.com", "Ada")
    client.post(f"/api/activities/{early}/attempts", json={"submitted": {"selected": "b"}})
    client.post(f"/api/activities/{early}/hints")
    client.post(f"/api/activities/{early}/attempts", json={"submitted": {"selected": "a"}})
    return ada, video_id


def test_students_and_guests_cannot_use_it(client: TestClient, db: Session) -> None:
    ada = register(client, "ada@example.com", "Ada")
    assert client.get("/api/staff/accounts").status_code == 403
    assert client.get(f"/api/staff/accounts/{ada}").status_code == 403
    assert client.delete(f"/api/staff/accounts/{ada}").status_code == 403
    client.cookies.clear()
    assert client.get("/api/staff/accounts").status_code == 401


def test_lists_every_account_newest_first_with_last_activity(
    client: TestClient, db: Session
) -> None:
    ada, _ = ada_does_some_work(client, db)
    grace = register(client, "grace@example.com", "Grace")
    make_staff(db, grace)

    rows = client.get("/api/staff/accounts").json()
    assert [(r["id"], r["email"], r["isStaff"]) for r in rows] == [
        (grace, "grace@example.com", True),
        # A student's email is masked in the list (NFR-S8, #146); their own page shows it.
        (ada, "a•••@example.com", False),
    ]
    assert rows[0]["lastActiveAt"] is None
    assert rows[1]["lastActiveAt"] is not None
    assert "passwordHash" not in rows[0]


def test_one_account_shows_totals_video_progress_and_recent_answers(
    client: TestClient, db: Session
) -> None:
    ada, video_id = ada_does_some_work(client, db)
    grace = register(client, "grace@example.com", "Grace")
    make_staff(db, grace)

    response = client.get(f"/api/staff/accounts/{ada}")
    assert response.status_code == 200
    body = response.json()
    assert body["displayName"] == "Ada"
    assert body["email"] == "ada@example.com"  # in full on their own page, unlike the list
    assert body["stats"] == {
        "attempts": 2,
        "correctAttempts": 1,
        "activitiesTried": 1,
        "activitiesPassed": 1,
        "hintsViewed": 1,
    }
    assert body["videos"] == [
        {"id": video_id, "title": "Meet BFS", "checkpointsPassed": 1, "checkpointsTotal": 2}
    ]
    assert [a["correct"] for a in body["recentAttempts"]] == [True, False]
    assert body["recentAttempts"][0]["activityTitle"] == "early"
    # Whether it was right, never what they answered.
    assert "submitted" not in response.text
    assert body["lastActiveAt"] is not None
    # The pilot files' name for her, to join the survey; never the account id (FR-10.3).
    assert body["pilotName"] == pseudonym(ada) != str(ada)


def test_an_account_with_no_activity_has_zeros(client: TestClient, db: Session) -> None:
    make_video(db)
    grace = register(client, "grace@example.com", "Grace")
    make_staff(db, grace)
    body = client.get(f"/api/staff/accounts/{grace}").json()
    assert body["stats"]["attempts"] == 0
    assert body["videos"][0]["checkpointsPassed"] == 0
    assert body["recentAttempts"] == []
    assert body["lastActiveAt"] is None


def test_missing_account_is_404(client: TestClient, db: Session) -> None:
    grace = register(client, "grace@example.com", "Grace")
    make_staff(db, grace)
    assert client.get("/api/staff/accounts/9999").status_code == 404
    assert client.delete("/api/staff/accounts/9999").status_code == 404


def test_delete_removes_the_account_and_its_data_and_ends_its_session(
    client: TestClient, db: Session
) -> None:
    ada, _ = ada_does_some_work(client, db)
    rewards.on_objective_result(db, ada, 1, "supported", {})  # a badge and points to delete too
    db.commit()
    assert db.scalar(select(func.count()).where(PointsEntry.user_id == ada))
    ada_cookies = dict(client.cookies)
    grace = register(client, "grace@example.com", "Grace")
    make_staff(db, grace)

    assert client.delete(f"/api/staff/accounts/{ada}").status_code == 204
    db.expire_all()
    assert db.get(User, ada) is None
    assert db.scalar(select(func.count()).where(Attempt.user_id == ada)) == 0
    assert db.scalar(select(func.count()).where(HintView.user_id == ada)) == 0
    assert db.scalar(select(func.count()).where(PointsEntry.user_id == ada)) == 0
    assert db.scalar(select(func.count()).where(UserBadge.user_id == ada)) == 0

    client.cookies.clear()
    for name, value in ada_cookies.items():
        client.cookies.set(name, value)
    assert client.get("/api/auth/me").status_code == 401
    # The email is free again.
    assert (
        client.post(
            "/api/auth/register",
            json={"email": "ada@example.com", "password": PASSWORD, "displayName": "Ada"},
        ).status_code
        == 201
    )


def test_nobody_can_delete_their_own_account_here(client: TestClient, db: Session) -> None:
    grace = register(client, "grace@example.com", "Grace")
    make_staff(db, grace)
    response = client.delete(f"/api/staff/accounts/{grace}")
    assert response.status_code == 409
    db.expire_all()
    assert db.get(User, grace) is not None


def test_mask_email_keeps_only_the_first_letter_and_the_domain() -> None:
    assert mask_email("ada@example.com") == "a•••@example.com"
    assert mask_email("x@up.ac.za") == "x•••@up.ac.za"
    assert mask_email("no-at-sign") == "•••"
