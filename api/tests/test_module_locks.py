"""An activity or a video is usable only once its module is open (FR-2.1, #137).

Before this, a brand-new account could read and answer all of module 6's mastery items, and open
hint 4 on them, without opening a single module, and come out "ready for the lecture" (FR-7.1 says
those items are unseen until the mastery check)."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Checkpoint, Module, ModuleProgress, User, Video
from app.seed import load

STUDENT = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}
ANY_ANSWER: dict[str, Any] = {"submitted": {"selected": "a"}}


def log_in(client: TestClient) -> int:
    assert client.post("/api/auth/register", json=STUDENT).status_code == 201
    return int(client.get("/api/auth/me").json()["id"])


def complete(db: Session, user_id: int, *, before: int) -> None:
    """Mark every module before position `before` complete, which opens that module."""
    for module in db.scalars(select(Module).where(Module.position < before)):
        db.add(ModuleProgress(user_id=user_id, module_id=module.id, status="complete"))
    db.commit()


def mastery_item(db: Session) -> Activity:
    return db.scalars(
        select(Activity)
        .where(Activity.module_id == 6, Activity.purpose == "mastery")
        .order_by(Activity.id)
    ).first()  # type: ignore[return-value]


def test_mastery_items_stay_locked_until_module_6_opens(client: TestClient, db: Session) -> None:
    load(db)
    user_id = log_in(client)
    item = mastery_item(db)

    assert client.get(f"/api/activities/{item.id}").status_code == 403
    assert client.post(f"/api/activities/{item.id}/attempts", json=ANY_ANSWER).status_code == 403
    assert client.post(f"/api/activities/{item.id}/hints").status_code == 403
    assert client.get(f"/api/activities/{item.id}/hints").status_code == 403
    assert client.get("/api/me/report").json()["ready"] is False

    complete(db, user_id, before=6)
    assert client.get(f"/api/activities/{item.id}").status_code == 200
    assert client.post(f"/api/activities/{item.id}/hints").status_code == 201


def test_a_module_s_activities_open_with_the_module(client: TestClient, db: Session) -> None:
    load(db)
    user_id = log_in(client)
    first = db.scalars(
        select(Activity).where(Activity.module_id == 0).order_by(Activity.id)
    ).first()
    later = db.scalars(
        select(Activity).where(Activity.module_id == 1).order_by(Activity.id)
    ).first()
    assert first is not None
    assert later is not None

    assert client.get(f"/api/activities/{first.id}").status_code == 200  # module 0 is always open
    assert client.get(f"/api/activities/{later.id}").status_code == 403
    complete(db, user_id, before=1)
    assert client.get(f"/api/activities/{later.id}").status_code == 200


def _video_with_checkpoint(db: Session, segment_id: int | None) -> tuple[Video, Activity]:
    question = Activity(
        id=99_001,
        kind="multiple_choice",
        title="Checkpoint",
        config={
            "prompt": "Which?",
            "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        },
        solution={"correct": "a", "feedback": {}},
    )
    video = Video(
        segment_id=segment_id,
        title="Graphs",
        media_path="/media/v.mp4",
        captions_path="/media/v.vtt",
        transcript="Words.",
        duration_seconds=60,
    )
    db.add_all([question, video])
    db.flush()
    db.add(Checkpoint(video_id=video.id, at_seconds=5, activity_id=question.id))
    db.commit()
    return video, question


def test_a_checkpoint_question_is_locked_with_the_module_that_plays_its_video(
    client: TestClient, db: Session
) -> None:
    load(db)
    video, question = _video_with_checkpoint(db, segment_id=103)  # module 1's first video
    user_id = log_in(client)

    assert client.get(f"/api/videos/{video.id}").status_code == 403
    assert client.get(f"/api/activities/{question.id}").status_code == 403
    assert (
        client.post(f"/api/activities/{question.id}/attempts", json=ANY_ANSWER).status_code == 403
    )

    complete(db, user_id, before=1)
    assert client.get(f"/api/videos/{video.id}").status_code == 200
    assert (
        client.post(f"/api/activities/{question.id}/attempts", json=ANY_ANSWER).status_code == 201
    )


def test_a_video_in_no_module_is_never_locked(client: TestClient, db: Session) -> None:
    """Staff make videos before placing them; until then the video page is how they're tested."""
    load(db)
    video, question = _video_with_checkpoint(db, segment_id=None)
    log_in(client)
    assert client.get(f"/api/videos/{video.id}").status_code == 200
    assert client.get(f"/api/activities/{question.id}").status_code == 200


def test_staff_can_open_any_activity_or_video_as_a_student(client: TestClient, db: Session) -> None:
    """The content editor's and the video editor's "Open as a student" must work on any item, so
    the team can check content: staff go past module locks and closed review paths."""
    load(db)
    video, question = _video_with_checkpoint(db, segment_id=103)  # module 1's first video
    user_id = log_in(client)
    db.get_one(User, user_id).is_staff = True
    db.commit()
    review_item = db.scalars(
        select(Activity).where(Activity.purpose == "review").order_by(Activity.id)
    ).first()
    assert review_item is not None

    for url in (
        f"/api/activities/{mastery_item(db).id}",
        f"/api/activities/{review_item.id}",
        f"/api/activities/{question.id}",
        f"/api/videos/{video.id}",
    ):
        assert client.get(url).status_code == 200, url
