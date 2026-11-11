"""Who may open which activity and video (#137; FR-2.1, FR-3, FR-7.1, FR-7.5).

On the committed course: a module's activities only once the module is open, a review path's
items only once module 6 has said "not yet" for its objective, a checkpoint question only once its
video is open, and nothing that is no longer part of the course. Staff may open everything.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from support import complete_modules_before

from app.models import (
    Activity,
    Attempt,
    Checkpoint,
    HintView,
    ModuleProgress,
    ObjectiveResult,
    PointsEntry,
    Segment,
    User,
    Video,
)
from app.routers.activities import MODULE_LOCKED, RETIRED, REVIEW_CLOSED
from app.routers.videos import LOCKED as VIDEO_LOCKED
from app.seed import load

STUDENT = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}
STAFF = {"email": "grace@example.com", "password": "Correct horse 2", "displayName": "Grace"}
MC_RIGHT = {"submitted": {"selected": "a"}}


@pytest.fixture
def committed(db: Session) -> Session:
    """The committed course (the fixtures in app/seed/), loaded as the seed loads it."""
    load(db)
    return db


def register(client: TestClient, who: dict[str, str] = STUDENT) -> int:
    assert client.post("/api/auth/register", json=who).status_code == 201
    return int(client.get("/api/auth/me").json()["id"])


def make_staff(db: Session, user_id: int) -> None:
    db.get_one(User, user_id).is_staff = True
    db.commit()


def first_submission(db: Session, activity_id: int) -> dict[str, Any]:
    """A submission in the right shape for the activity (not necessarily right)."""
    activity = db.get_one(Activity, activity_id)
    match activity.kind:
        case "multiple_choice":
            return {"selected": activity.config["options"][0]["id"]}
        case "parsons" | "fix_the_bug":
            return {"order": []}
        case "fill_in":
            return {"answers": {}}
        case "matching":
            return {"pairs": {}}
        case "choose_tests":
            return {"selected": []}
        case "trace":
            return {"rows": []}
    raise AssertionError(activity.kind)


def every_route(client: TestClient, db: Session, activity_id: int) -> list[tuple[str, int, Any]]:
    """GET, answer, GET hints and reveal a hint: (route, status, detail) for each."""
    body = {"submitted": first_submission(db, activity_id)}
    answers = [
        ("GET", client.get(f"/api/activities/{activity_id}")),
        ("attempt", client.post(f"/api/activities/{activity_id}/attempts", json=body)),
        ("GET hints", client.get(f"/api/activities/{activity_id}/hints")),
        ("hint", client.post(f"/api/activities/{activity_id}/hints")),
    ]
    return [(name, r.status_code, r.json().get("detail") if r.status_code >= 400 else None)
            for name, r in answers]  # fmt: skip


def all_refused(
    client: TestClient, db: Session, activity_id: int, status: int, detail: str
) -> None:
    assert every_route(client, db, activity_id) == [
        ("GET", status, detail),
        ("attempt", status, detail),
        ("GET hints", status, detail),
        ("hint", status, detail),
    ]


def count(db: Session, model: Any, user_id: int) -> int:
    db.expire_all()
    return db.scalars(select(func.count()).select_from(model).where(model.user_id == user_id)).one()


# --- Modules (FR-2.1) ---------------------------------------------------------------------------


def test_a_new_student_cannot_read_answer_or_hint_any_mastery_item(
    client: TestClient, committed: Session
) -> None:
    """The bug in #137: a brand-new account answered all 24 module 6 items and was 'ready'."""
    db = committed
    user_id = register(client)
    items = db.scalars(
        select(Activity.id).where(Activity.module_id == 6, Activity.purpose == "mastery")
    ).all()
    assert len(items) == 24
    for item in items:
        all_refused(client, db, item, 403, MODULE_LOCKED)
    # Nothing was recorded or revealed, and the student is no closer to "ready".
    assert count(db, Attempt, user_id) == 0
    assert count(db, HintView, user_id) == 0
    assert count(db, PointsEntry, user_id) == 0
    assert count(db, ObjectiveResult, user_id) == 0
    report = client.get("/api/me/report").json()
    assert report["ready"] is False
    assert {o["state"] for o in report["objectives"]} == {"not_attempted"}


def test_module_6_items_open_with_module_6(client: TestClient, committed: Session) -> None:
    db = committed
    register(client)
    complete_modules_before(db, STUDENT["email"], 6)
    statuses = {m["id"]: m["status"] for m in client.get("/api/modules").json()}
    assert statuses[6] == "open"
    assert [s for _, s, _ in every_route(client, db, 601)] == [200, 201, 200, 201]


def test_each_modules_activities_open_exactly_when_the_module_does(
    client: TestClient, committed: Session
) -> None:
    """For every module: its practice, retrieval and skip-check activities are 403 while it is
    locked and usable once it opens. Module 0 (the diagnostic) is open from the start."""
    db = committed
    user_id = register(client)
    modules = db.scalars(select(Activity.module_id).distinct()).all()
    for module_id in sorted(m for m in modules if m is not None):
        activities = db.scalars(select(Activity.id).where(Activity.module_id == module_id)).all()
        statuses = {m["id"]: m["status"] for m in client.get("/api/modules").json()}
        if statuses[module_id] == "locked":
            for activity in activities:
                response = client.get(f"/api/activities/{activity}")
                assert (response.status_code, response.json()["detail"]) == (403, MODULE_LOCKED)
        db.query(ModuleProgress).filter(ModuleProgress.user_id == user_id).delete()
        db.commit()
        complete_modules_before(db, STUDENT["email"], module_id)
        for activity in activities:
            assert client.get(f"/api/activities/{activity}").status_code == 200, activity


def test_module_0s_diagnostic_is_open_to_a_new_student(
    client: TestClient, committed: Session
) -> None:
    db = committed
    register(client)
    diagnostic = db.scalars(select(Activity.id).where(Activity.purpose == "diagnostic")).all()
    assert diagnostic
    for activity in diagnostic:
        assert [s for _, s, _ in every_route(client, committed, activity)][:3] == [200, 201, 200]


def test_a_retrieval_item_belongs_to_its_module(client: TestClient, committed: Session) -> None:
    """Module 2's recall questions are asked before module 2 starts, so they open with it."""
    db = committed
    register(client)
    retrieval = db.scalars(
        select(Activity.id).where(Activity.module_id == 2, Activity.purpose == "retrieval")
    ).all()
    assert retrieval
    all_refused(client, db, retrieval[0], 403, MODULE_LOCKED)
    complete_modules_before(db, STUDENT["email"], 2)
    assert [s for _, s, _ in every_route(client, db, retrieval[0])][:3] == [200, 201, 200]


def test_an_activity_a_module_segment_shows_follows_that_module(
    client: TestClient, committed: Session
) -> None:
    """An activity with no `module_id` (made in a staff editor) that a module's segment shows is
    open exactly when that module is."""
    db = committed
    activity = Activity(
        kind="multiple_choice",
        title="Made by staff",
        config={"prompt": "Q", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]},
        solution={"correct": "a"},
    )
    db.add(activity)
    db.flush()
    db.add(Segment(module_id=3, position=99, kind="activity", title="New", activity_id=activity.id))
    db.commit()
    register(client)
    all_refused(client, db, activity.id, 403, MODULE_LOCKED)
    complete_modules_before(db, STUDENT["email"], 3)
    assert client.get(f"/api/activities/{activity.id}").status_code == 200


def skip_check(db: Session, module_id: int, activity_id: int) -> None:
    """A worked example in `module_id` that names `activity_id` as its skip check (FR-8.2)."""
    db.add(
        Segment(
            module_id=module_id,
            position=98,
            kind="worked_example",
            title="Skippable",
            skip_check_activity_id=activity_id,
        )
    )
    db.commit()


def test_a_skip_check_never_opens_a_mastery_item(client: TestClient, committed: Session) -> None:
    """Module 0 is open from the start; naming 601 as one of its skip checks must not open it."""
    db = committed
    skip_check(db, 0, 601)
    register(client)
    all_refused(client, db, 601, 403, MODULE_LOCKED)


def test_a_skip_check_never_opens_another_modules_item(
    client: TestClient, committed: Session
) -> None:
    db = committed
    skip_check(db, 0, 401)  # a module 4 practice item, named by open module 0
    register(client)
    all_refused(client, db, 401, 403, MODULE_LOCKED)


def test_a_skip_check_of_no_module_opens_with_the_module_that_names_it(
    client: TestClient, committed: Session
) -> None:
    db = committed
    activity = Activity(
        kind="multiple_choice",
        title="Quick check",
        config={"prompt": "Q", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]},
        solution={"correct": "a"},
    )
    db.add(activity)
    db.commit()
    skip_check(db, 1, activity.id)
    register(client)
    all_refused(client, db, activity.id, 403, MODULE_LOCKED)
    complete_modules_before(db, STUDENT["email"], 1)
    assert client.get(f"/api/activities/{activity.id}").status_code == 200


# --- Review paths (FR-7.5) ----------------------------------------------------------------------


def review_items(db: Session, objective: int) -> list[int]:
    return [
        a
        for a in db.scalars(
            select(Segment.activity_id)
            .where(Segment.review_objective_id == objective)
            .order_by(Segment.position)
        )
        if a is not None
    ]


def test_review_path_items_stay_closed_even_with_module_6_open(
    client: TestClient, committed: Session
) -> None:
    db = committed
    register(client)
    complete_modules_before(db, STUDENT["email"], 6)
    for item in review_items(db, 1):
        all_refused(client, db, item, 403, REVIEW_CLOSED)


def test_a_review_path_opens_when_module_6_says_not_yet(
    client: TestClient, committed: Session
) -> None:
    db = committed
    register(client)
    complete_modules_before(db, STUDENT["email"], 6)
    objective_1 = db.scalars(
        select(Activity).where(Activity.module_id == 6, Activity.objective_id == 1)
    ).all()
    for item in objective_1:  # every one wrong
        body = {"submitted": first_submission(db, item.id)}
        if item.kind == "multiple_choice":
            options = [o["id"] for o in item.config["options"]]
            body["submitted"]["selected"] = next(
                o for o in options if o != item.solution["correct"]
            )
        assert client.post(f"/api/activities/{item.id}/attempts", json=body).status_code == 201
    states = {o["id"]: o["state"] for o in client.get("/api/me/report").json()["objectives"]}
    assert states[1] == "not_yet"
    for step in review_items(db, 1):
        assert client.get(f"/api/activities/{step}").status_code == 200
    for step in review_items(db, 2):  # objective 2's path is still closed
        assert client.get(f"/api/activities/{step}").status_code == 403


def test_staff_may_preview_a_review_path_that_is_closed_for_students(
    client: TestClient, committed: Session
) -> None:
    db = committed
    make_staff(db, register(client, STAFF))
    response = client.get("/api/me/review/3")
    assert response.status_code == 200
    body = response.json()
    assert body["progress"] == {
        "answered": 0,
        "total": len([s for s in body["steps"] if s["purpose"] == "mastery"]),
    }
    client.post("/api/auth/logout")
    register(client)
    assert client.get("/api/me/review/3").status_code == 403


# --- Videos and their checkpoint questions (FR-3) -----------------------------------------------


def video_with_checkpoint(db: Session, segment_id: int | None) -> tuple[int, int]:
    """A video on `segment_id` (None: placed nowhere) with one checkpoint question."""
    question = Activity(
        kind="multiple_choice",
        title="Checkpoint",
        visible=True,
        config={"prompt": "Q", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]},
        solution={"correct": "a"},
    )
    video = Video(
        segment_id=segment_id,
        title="BFS",
        media_path="/media/videos/bfs.mp4",
        captions_path="/media/videos/bfs.vtt",
        transcript="Text",
        duration_seconds=60,
    )
    db.add_all([question, video])
    db.flush()
    db.add(Checkpoint(video_id=video.id, at_seconds=10, activity_id=question.id))
    db.commit()
    return video.id, question.id


def test_a_checkpoint_question_opens_with_its_videos_module(
    client: TestClient, committed: Session
) -> None:
    db = committed
    segment = db.scalars(select(Segment).where(Segment.module_id == 2, Segment.kind == "video"))
    video_id, question = video_with_checkpoint(db, segment.first().id)  # type: ignore[union-attr]
    register(client)
    response = client.get(f"/api/videos/{video_id}")
    assert (response.status_code, response.json()["detail"]) == (403, VIDEO_LOCKED)
    all_refused(client, db, question, 403, MODULE_LOCKED)

    complete_modules_before(db, STUDENT["email"], 2)
    assert client.get(f"/api/videos/{video_id}").status_code == 200
    assert client.post(f"/api/activities/{question}/attempts", json=MC_RIGHT).status_code == 201
    checkpoints = client.get(f"/api/videos/{video_id}").json()["checkpoints"]
    assert [c["passed"] for c in checkpoints] == [True]


def test_a_video_placed_nowhere_and_its_questions_stay_open(
    client: TestClient, committed: Session
) -> None:
    """The staff video editor makes videos before anyone places them; a link to one keeps
    working, as before #137."""
    video_id, question = video_with_checkpoint(committed, None)
    register(client)
    assert client.get(f"/api/videos/{video_id}").status_code == 200
    assert client.post(f"/api/activities/{question}/attempts", json=MC_RIGHT).status_code == 201


def test_a_video_on_a_review_path_opens_with_the_path(
    client: TestClient, committed: Session
) -> None:
    db = committed
    first_step = db.scalars(select(Segment).where(Segment.review_objective_id == 1)).first()
    assert first_step is not None
    video_id, question = video_with_checkpoint(db, first_step.id)
    register(client)
    complete_modules_before(db, STUDENT["email"], 6)
    assert client.get(f"/api/videos/{video_id}").status_code == 403
    all_refused(client, db, question, 403, REVIEW_CLOSED)


# --- Activities that are no longer in the course, and staff ------------------------------------


def retired(db: Session) -> int:
    """An activity the seed retired: kept for its history, in no module, path or video."""
    activity = Activity(
        kind="multiple_choice",
        title="Old",
        visible=False,
        config={"prompt": "Q", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]},
        solution={"correct": "a"},
    )
    db.add(activity)
    db.commit()
    return activity.id


def test_a_retired_activity_is_404_for_students(client: TestClient, committed: Session) -> None:
    """It still earned 10 points before #137."""
    db = committed
    activity = retired(db)
    user_id = register(client)
    all_refused(client, db, activity, 404, RETIRED)
    assert count(db, PointsEntry, user_id) == 0


def test_staff_may_open_any_activity_and_video_to_preview_it(
    client: TestClient, committed: Session
) -> None:
    db = committed
    make_staff(db, register(client, STAFF))
    segment = db.scalars(select(Segment).where(Segment.module_id == 4, Segment.kind == "video"))
    video_id, question = video_with_checkpoint(db, segment.first().id)  # type: ignore[union-attr]
    for activity in [601, retired(db), *review_items(db, 3), question]:
        assert client.get(f"/api/activities/{activity}").status_code == 200, activity
    assert client.post("/api/activities/601/attempts", json=MC_RIGHT).status_code == 201
    assert client.post("/api/activities/601/hints").status_code == 201
    assert client.get(f"/api/videos/{video_id}").status_code == 200


def test_a_missing_activity_is_still_404(client: TestClient, committed: Session) -> None:
    register(client)
    for path in ("/api/activities/999999", "/api/activities/0"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()["detail"] == "This activity does not exist."
