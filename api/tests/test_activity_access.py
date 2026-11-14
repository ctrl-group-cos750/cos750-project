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
from support import complete_modules_before, wrong_answer

from app.models import (
    Activity,
    Attempt,
    Checkpoint,
    HintView,
    ObjectiveResult,
    PointsEntry,
    Segment,
    User,
    Video,
)
from app.routers.activities import (
    MODULE_LOCKED,
    PRACTICE_FIRST,
    QUEST_CLOSED,
    QUICK_CHECK,
    RETIRED,
    REVIEW_CLOSED,
)
from app.routers.videos import LOCKED as VIDEO_LOCKED
from app.routers.videos import MODULE_LOCKED as VIDEO_MODULE_LOCKED
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
    """A real answer to the activity (wrong): an empty one would be refused with 422."""
    return wrong_answer(db.get_one(Activity, activity_id))


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
    assert len(items) == 28  # 24, and objective 8's four (#70)
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
    # The hint is 409: a mastery check item gives none once it is answered (#144).
    assert [s for _, s, _ in every_route(client, db, 601)] == [200, 201, 200, 409]


def test_each_modules_activities_open_exactly_when_the_module_does(
    client: TestClient, committed: Session
) -> None:
    """The student chooses where to start (#214): every activity of modules 0 to 5 is usable from
    the start, except hidden support (#172), bonus quests until their module is complete, and quick
    check questions (FR-8.2), which are only asked in the quick check. Module 6's are 403 until
    module 6 opens."""
    db = committed
    register(client)
    on_base = set(
        db.scalars(
            select(Segment.activity_id).where(
                Segment.activity_id.is_not(None), Segment.support_for.is_(None)
            )
        )
    )
    on_support = set(
        db.scalars(
            select(Segment.activity_id).where(
                Segment.activity_id.is_not(None), Segment.support_for.is_not(None)
            )
        )
    )
    support_only = on_support - on_base
    statuses = {m["id"]: m["status"] for m in client.get("/api/modules").json()}
    assert [s for _, s in sorted(statuses.items())] == ["open"] * 6 + ["locked"]
    quick_check = set(db.scalars(select(Activity.id).where(Activity.purpose == "test_out")))
    assert len(quick_check) == 20
    for activity in db.scalars(select(Activity).where(Activity.module_id.in_(range(6)))):
        response = client.get(f"/api/activities/{activity.id}")
        if activity.id in quick_check:
            assert (response.status_code, response.json()["detail"]) == (403, QUICK_CHECK)
        elif activity.purpose == "bonus":
            assert (response.status_code, response.json()["detail"]) == (403, QUEST_CLOSED)
        else:
            assert response.status_code == (403 if activity.id in support_only else 200), (
                activity.id
            )
    module_6 = db.scalars(select(Activity.id).where(Activity.module_id == 6)).all()
    for activity_id in module_6:
        response = client.get(f"/api/activities/{activity_id}")
        assert (response.status_code, response.json()["detail"]) == (403, MODULE_LOCKED)
    complete_modules_before(db, STUDENT["email"], 6)
    for activity_id in module_6:
        assert client.get(f"/api/activities/{activity_id}").status_code == 200


def test_quick_check_items_are_refused_on_every_activity_route(
    client: TestClient, committed: Session
) -> None:
    """They are answered only in the quick check, all at once: never one by one, with hints, or
    with their result shown early (FR-8.2, #214). Staff may still preview them."""
    db = committed
    user_id = register(client)
    for activity_id in (103, 150, 314, 552):
        all_refused(client, db, activity_id, 403, QUICK_CHECK)
    assert count(db, Attempt, user_id) == 0
    assert count(db, HintView, user_id) == 0
    make_staff(db, user_id)
    assert client.get("/api/activities/103").status_code == 200


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
    """A module's recall questions are asked before it starts, so they open with it: module 2's
    from the start (#214), module 6's once module 6 opens."""
    db = committed
    register(client)
    retrieval = db.scalars(
        select(Activity.id).where(Activity.module_id == 2, Activity.purpose == "retrieval")
    ).all()
    assert retrieval
    assert [s for _, s, _ in every_route(client, db, retrieval[0])][:3] == [200, 201, 200]
    all_refused(client, db, 625, 403, MODULE_LOCKED)  # module 6's
    complete_modules_before(db, STUDENT["email"], 6)
    assert [s for _, s, _ in every_route(client, db, 625)][:3] == [200, 201, 200]


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
    db.add(Segment(module_id=6, position=99, kind="activity", title="New", activity_id=activity.id))
    db.commit()
    register(client)
    all_refused(client, db, activity.id, 403, MODULE_LOCKED)
    complete_modules_before(db, STUDENT["email"], 6)
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
    skip_check(db, 0, 625)  # a module 6 recall item, named by open module 0
    register(client)
    all_refused(client, db, 625, 403, MODULE_LOCKED)


def test_a_skip_check_never_opens_a_review_path_item(
    client: TestClient, committed: Session
) -> None:
    """1101 is objective 1's review practice (no module): a module 0 segment naming it as a skip
    check must not open it before the path opens."""
    db = committed
    item = review_items(db, 1)[0]
    assert db.get_one(Activity, item).module_id is None
    skip_check(db, 0, item)
    register(client)
    all_refused(client, db, item, 403, REVIEW_CLOSED)


def test_a_skip_check_of_no_module_opens_with_the_module_that_names_it(
    client: TestClient, committed: Session
) -> None:
    """A diagnostic skip check opens with its module. (A practice item used only as a skip check
    stays shut, and a quick check item is only asked in the quick check: the tests above.)"""
    db = committed
    activity = Activity(
        kind="multiple_choice",
        title="Quick check",
        config={"prompt": "Q", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]},
        solution={"correct": "a"},
        purpose="diagnostic",
    )
    db.add(activity)
    db.commit()
    skip_check(db, 6, activity.id)
    register(client)
    all_refused(client, db, activity.id, 403, MODULE_LOCKED)
    complete_modules_before(db, STUDENT["email"], 6)
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
        assert client.post(f"/api/activities/{item.id}/attempts", json=body).status_code == 201
    # Nothing is marked until the whole check is answered (#144): the rest of it right.
    user_id = db.scalar(select(User.id).where(User.email == STUDENT["email"]))
    rest = db.scalars(
        select(Activity.id).where(
            Activity.module_id == 6, Activity.purpose == "mastery", Activity.objective_id != 1
        )
    ).all()
    for activity_id in rest:
        db.add(
            Attempt(
                user_id=user_id,
                activity_id=activity_id,
                submitted={},
                correct=True,
                score=1.0,
                detail={},
                hint_level=0,
            )
        )
    db.commit()
    states = {o["id"]: o["state"] for o in client.get("/api/me/report").json()["objectives"]}
    assert states[1] == "not_yet"
    steps = review_items(db, 1)
    purposes = {a.id: a.purpose for a in db.scalars(select(Activity).where(Activity.id.in_(steps)))}
    practice = [s for s in steps if purposes[s] == "review"]
    fresh = [s for s in steps if purposes[s] == "mastery"]
    for step in practice:
        assert client.get(f"/api/activities/{step}").status_code == 200
    # The fresh items wait for the practice (review of 13 Nov, Critical 1).
    for step in fresh:
        refused = client.get(f"/api/activities/{step}")
        assert (refused.status_code, refused.json()["detail"]) == (403, PRACTICE_FIRST)
        assert client.post(f"/api/activities/{step}/hints").status_code == 403
    for step in practice:  # answered twice: done, as in a module (FR-2.7)
        for _ in range(2):
            body = {"submitted": first_submission(db, step)}
            assert client.post(f"/api/activities/{step}/attempts", json=body).status_code == 201
    for step in fresh:
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
    segment = db.scalars(select(Segment).where(Segment.module_id == 6))  # the one locked module
    video_id, question = video_with_checkpoint(db, segment.first().id)  # type: ignore[union-attr]
    register(client)
    response = client.get(f"/api/videos/{video_id}")
    assert (response.status_code, response.json()["detail"]) == (403, VIDEO_MODULE_LOCKED)
    all_refused(client, db, question, 403, MODULE_LOCKED)

    complete_modules_before(db, STUDENT["email"], 6)
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
    response = client.get(f"/api/videos/{video_id}")
    assert (response.status_code, response.json()["detail"]) == (403, VIDEO_LOCKED)
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
    # The hint first: once answered right, no more hints are given, to staff too (#158).
    assert client.post("/api/activities/601/hints").status_code == 201
    right = {"submitted": {"selected": "d"}}  # 601's key since #214 (C5)
    assert client.post("/api/activities/601/attempts", json=right).status_code == 201
    assert client.get(f"/api/videos/{video_id}").status_code == 200


def test_a_missing_activity_is_still_404(client: TestClient, committed: Session) -> None:
    register(client)
    for path in ("/api/activities/999999", "/api/activities/0"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()["detail"] == "This activity does not exist."
