"""End-to-end tests for the module-map and progress endpoints (FR-2).

GET  /api/modules                      → list[ModuleOut]
GET  /api/modules/{id}                 → ModuleDetailOut  (404 missing, 403 locked)
POST /api/modules/{id}/position        → ModuleDetailOut  (commits progress)

Seeding strategy: insert Module + Segment rows directly in the test db session — the
same approach test_seed.py uses when it inserts Module/ModuleProgress/User rows directly.
Using 3 modules (numbers 0, 1, 2) with 2 segments each is enough to exercise the opening rule
(every module open but the last, which opens once the ones between the first and it are done,
#214) and the completion logic while keeping the setup minimal.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    Activity,
    Attempt,
    Checkpoint,
    Event,
    Hint,
    Module,
    ModuleProgress,
    Objective,
    PointsEntry,
    Segment,
    User,
    UserBadge,
    Video,
)
from app.services import modules as modules_service
from app.services.mastery import counts
from app.services.modules import backfill_module_rewards

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALICE = {"email": "alice@example.com", "password": "Correct horse 1", "displayName": "Alice"}
BOB = {"email": "bob@example.com", "password": "Correct horse 2", "displayName": "Bob"}


def _make_modules(db: Session) -> tuple[int, int, int]:
    """Insert 3 modules (ids 0-2: a module's id is its number), each with 2 segments.

    Returns the three module IDs in order.
    """
    m0 = Module(
        id=0, slug="warm-up", title="Warm-up", goals=["Goal 0."], estimated_minutes=5, position=0
    )
    m1 = Module(
        id=1, slug="graphs", title="Graphs", goals=["Goal 1."], estimated_minutes=12, position=1
    )
    m2 = Module(
        id=2,
        slug="python-graphs",
        title="A graph in Python",
        goals=["Goal 2."],
        estimated_minutes=10,
        position=2,
    )
    db.add_all([m0, m1, m2])
    db.flush()  # populate ids before creating segments

    # 2 segments per module, positions 0 and 1.
    for mod in (m0, m1, m2):
        db.add(
            Segment(
                module_id=mod.id,
                position=0,
                kind="text",
                title=f"{mod.title} intro",
                body="Body text.",
            )
        )
        db.add(
            Segment(
                module_id=mod.id,
                position=1,
                kind="worked_example",
                title=f"{mod.title} example",
                body="Example text.",
            )
        )
    db.commit()
    return m0.id, m1.id, m2.id


def _register_and_login(client: TestClient, user: dict[str, str]) -> None:
    """Register *user*; the TestClient stores the session cookie automatically."""
    assert client.post("/api/auth/register", json=user).status_code == 201


def _logout(client: TestClient) -> None:
    client.post("/api/auth/logout")


# ---------------------------------------------------------------------------
# 1. GET /api/modules — initial states
# ---------------------------------------------------------------------------


def test_list_modules_returns_all_modules_with_initial_states(
    client: TestClient, db: Session
) -> None:
    """Every module but the last is open for a brand-new student; the last (the mastery check)
    is locked until the modules between the first and it are done (#214)."""
    _make_modules(db)
    _register_and_login(client, ALICE)

    res = client.get("/api/modules")
    assert res.status_code == 200
    modules = res.json()
    assert len(modules) == 3  # 3 modules were seeded

    # Returned in position order.
    assert [m["number"] for m in modules] == [0, 1, 2]

    # Status — the student chooses where to start; only the last module is locked.
    assert modules[0]["status"] == "open"
    assert modules[1]["status"] == "open"
    assert modules[2]["status"] == "locked"
    # The first module is the one recommended.
    assert [m["recommended"] for m in modules] == [True, False, False]


def test_list_modules_includes_estimated_minutes_and_segment_count(
    client: TestClient, db: Session
) -> None:
    """Each item in the map has estimatedMinutes and segmentCount."""
    _make_modules(db)
    _register_and_login(client, ALICE)

    modules = client.get("/api/modules").json()
    for mod in modules:
        assert "estimatedMinutes" in mod
        assert mod["estimatedMinutes"] > 0
        assert mod["segmentCount"] == 2  # 2 segments per module in test data


# ---------------------------------------------------------------------------
# 2. GET /api/modules/{id} — module detail
# ---------------------------------------------------------------------------


def test_get_module_detail_returns_goals_and_ordered_segments(
    client: TestClient, db: Session
) -> None:
    """Detail for module 0 includes goals and segments in position order."""
    m0_id, _, _ = _make_modules(db)
    _register_and_login(client, ALICE)

    res = client.get(f"/api/modules/{m0_id}")
    assert res.status_code == 200
    body = res.json()

    assert body["goals"] == ["Goal 0."]
    segs = body["segments"]
    assert len(segs) == 2
    # Segments come back in position order.
    assert [s["position"] for s in segs] == [0, 1]
    assert segs[0]["kind"] == "text"
    assert segs[1]["kind"] == "worked_example"


def test_module_retrieval_items_are_answer_free_and_attempts_do_not_count_as_mastery(
    client: TestClient, db: Session
) -> None:
    _, _, module_id = _make_modules(db)
    activity = Activity(
        id=201,
        kind="multiple_choice",
        title="Recall adjacency lists",
        module_id=module_id,
        purpose="retrieval",
        config={
            "prompt": "What does an adjacency list store?",
            "options": [
                {"id": "neighbors", "label": "Connected vertices"},
                {"id": "counts", "label": "Visit counts"},
            ],
        },
        solution={"correct": "neighbors"},
    )
    db.add(activity)
    db.commit()
    _register_and_login(client, ALICE)
    client.post("/api/modules/0/position", json={"segmentPosition": 1})
    client.post("/api/modules/1/position", json={"segmentPosition": 1})

    detail = client.get(f"/api/modules/{module_id}").json()
    # The page loads the question from the activity endpoint, which leaves out the answer.
    assert detail["retrieval"] == [
        {"id": 201, "title": "Recall adjacency lists", "answered": False}
    ]
    blocked = client.post(f"/api/modules/{module_id}/position", json={"segmentPosition": 0})
    assert blocked.status_code == 409

    submitted = client.post(
        "/api/activities/201/attempts", json={"submitted": {"selected": "neighbors"}}
    )
    assert submitted.status_code == 201
    stored = db.scalar(select(Attempt).where(Attempt.activity_id == 201))
    assert stored is not None
    assert stored.correct
    assert not counts(activity)
    detail = client.get(f"/api/modules/{module_id}").json()
    assert detail["retrieval"][0]["answered"]  # a later visit resumes past it
    assert (
        client.post(f"/api/modules/{module_id}/position", json={"segmentPosition": 0}).status_code
        == 200
    )


def test_a_module_completed_before_its_retrieval_questions_can_still_be_reread(
    client: TestClient, db: Session
) -> None:
    """The retrieval gate (FR-2.4) holds back a module being started, not one already done."""
    _, _, module_id = _make_modules(db)
    _register_and_login(client, ALICE)
    for number in (0, 1, module_id):
        client.post(f"/api/modules/{number}/position", json={"segmentPosition": 0})
        client.post(f"/api/modules/{number}/position", json={"segmentPosition": 1})
    assert client.get(f"/api/modules/{module_id}").json()["status"] == "complete"

    # The question is added after the student finished the module.
    db.add(
        Activity(
            id=201,
            kind="multiple_choice",
            title="Recall adjacency lists",
            module_id=module_id,
            purpose="retrieval",
            config={"prompt": "?", "options": [{"id": "a", "label": "A"}]},
            solution={"correct": "a"},
        )
    )
    db.commit()
    reread = client.post(f"/api/modules/{module_id}/position", json={"segmentPosition": 0})
    assert reread.status_code == 200
    assert reread.json()["status"] == "complete"

    # A student who has not finished it is still asked first.
    _logout(client)
    _register_and_login(client, BOB)
    client.post("/api/modules/0/position", json={"segmentPosition": 1})
    client.post("/api/modules/1/position", json={"segmentPosition": 1})
    blocked = client.post(f"/api/modules/{module_id}/position", json={"segmentPosition": 0})
    assert blocked.status_code == 409


def test_get_missing_module_is_404(client: TestClient, db: Session) -> None:
    _make_modules(db)
    _register_and_login(client, ALICE)
    assert client.get("/api/modules/9999").status_code == 404


# ---------------------------------------------------------------------------
# 3. GET /api/modules/{id} — 403 for locked module
# ---------------------------------------------------------------------------


def test_get_locked_module_is_403(client: TestClient, db: Session) -> None:
    """The last module is locked until the ones between the first and it are done: 403."""
    _, _, m2_id = _make_modules(db)
    _register_and_login(client, ALICE)

    res = client.get(f"/api/modules/{m2_id}")
    assert res.status_code == 403
    assert "mastery check" in res.json()["detail"]


def test_get_module_2_locked_until_module_1_complete(client: TestClient, db: Session) -> None:
    """Even after starting module 0, module 2 stays locked until module 1 is done."""
    m0_id, _, m2_id = _make_modules(db)
    _register_and_login(client, ALICE)

    # Advance module 0 but do not complete it (position 0 out of last-index 1).
    client.post(f"/api/modules/{m0_id}/position", json={"segmentPosition": 0})
    assert client.get(f"/api/modules/{m2_id}").status_code == 403


# ---------------------------------------------------------------------------
# 4. POST /api/modules/{id}/position — saves progress
# ---------------------------------------------------------------------------


def test_post_position_saves_and_returns_updated_current_segment_position(
    client: TestClient, db: Session
) -> None:
    """Calling POST /position with segmentPosition=0 is persisted and reflected in the response."""
    m0_id, _, _ = _make_modules(db)
    _register_and_login(client, ALICE)

    res = client.post(f"/api/modules/{m0_id}/position", json={"segmentPosition": 0})
    assert res.status_code == 200
    body = res.json()
    assert body["currentSegmentPosition"] == 0
    assert body["status"] == "in_progress"

    # Advance to position 1 (still not the last index for a 2-segment module → wait, 1 IS last).
    # Actually position 1 = last index (2 segments → last_index = 1) so that completes it.
    # Verify in_progress first by posting position 0 again to confirm idempotency.
    res2 = client.post(f"/api/modules/{m0_id}/position", json={"segmentPosition": 0})
    assert res2.json()["currentSegmentPosition"] == 0


# ---------------------------------------------------------------------------
# 5. Completing the last segment marks the module 'complete'
# ---------------------------------------------------------------------------


def test_reaching_last_segment_completes_the_module(client: TestClient, db: Session) -> None:
    """Posting segmentPosition = last index (1 for a 2-segment module) → status 'complete'."""
    m0_id, _, _ = _make_modules(db)
    _register_and_login(client, ALICE)

    # last index = 2 - 1 = 1.
    res = client.post(f"/api/modules/{m0_id}/position", json={"segmentPosition": 1})
    assert res.status_code == 200
    assert res.json()["status"] == "complete"


def test_jumping_ahead_is_refused_so_a_module_cant_be_finished_unread(
    client: TestClient, db: Session
) -> None:
    """A position more than one past the furthest reached is 409, and nothing is saved."""
    m0_id, _, _ = _make_modules(db)
    _register_and_login(client, ALICE)

    res = client.post(f"/api/modules/{m0_id}/position", json={"segmentPosition": 5})
    assert res.status_code == 409
    assert client.get(f"/api/modules/{m0_id}").json()["status"] == "open"


def test_going_back_keeps_the_furthest_position_and_the_completion(
    client: TestClient, db: Session
) -> None:
    """Rereading an earlier segment of a finished module doesn't un-finish it, and doesn't
    re-lock the next module the student hasn't started yet."""
    m0_id, m1_id, _ = _make_modules(db)
    _register_and_login(client, ALICE)
    client.post(f"/api/modules/{m0_id}/position", json={"segmentPosition": 1})

    res = client.post(f"/api/modules/{m0_id}/position", json={"segmentPosition": 0})
    assert res.status_code == 200
    assert res.json()["status"] == "complete"
    assert res.json()["currentSegmentPosition"] == 1
    statuses = {m["id"]: m["status"] for m in client.get("/api/modules").json()}
    assert statuses[m1_id] == "open"


def test_a_review_segment_is_not_part_of_any_module(client: TestClient, db: Session) -> None:
    """Segments of an objective's review path (#23) belong to no module."""
    m0_id, _, _ = _make_modules(db)
    db.add(Objective(id=1, text="o", bloom_level="b", criterion="c", pass_fraction=0.8))
    db.flush()
    db.add(Segment(review_objective_id=1, position=0, kind="text", title="Review", body="x"))
    db.commit()
    _register_and_login(client, ALICE)

    assert len(client.get(f"/api/modules/{m0_id}").json()["segments"]) == 2
    counts = {m["id"]: m["segmentCount"] for m in client.get("/api/modules").json()}
    assert counts[m0_id] == 2


def test_a_video_segment_carries_the_video_that_points_at_it(
    client: TestClient, db: Session
) -> None:
    """Videos are made in the app and point at their segment (Video.segment_id)."""
    m0_id, _, _ = _make_modules(db)
    segment = Segment(module_id=m0_id, position=2, kind="video", title="Watch")
    db.add(segment)
    db.flush()
    video = Video(
        title="BFS",
        media_path="/media/bfs.mp4",
        captions_path="/media/bfs.vtt",
        transcript="",
        duration_seconds=60,
        segment_id=segment.id,
    )
    db.add(video)
    db.commit()
    _register_and_login(client, ALICE)

    segments = client.get(f"/api/modules/{m0_id}").json()["segments"]
    assert segments[2]["videoId"] == video.id
    assert segments[0]["videoId"] is None


# ---------------------------------------------------------------------------
# 6. Unlocking: module N+1 becomes 'open' after module N is 'complete'
# ---------------------------------------------------------------------------


def test_completing_module_0_unlocks_module_1(client: TestClient, db: Session) -> None:
    """After module 0 is complete, module 1 appears as 'open' on the list endpoint."""
    m0_id, _m1_id, _ = _make_modules(db)
    _register_and_login(client, ALICE)

    # Complete module 0.
    client.post(f"/api/modules/{m0_id}/position", json={"segmentPosition": 1})

    # Module 1 should now be open.
    modules = client.get("/api/modules").json()
    status_by_number = {m["number"]: m["status"] for m in modules}
    assert status_by_number[0] == "complete"
    assert status_by_number[1] == "open"
    assert status_by_number[2] == "locked"


def test_a_student_may_start_with_a_later_module(client: TestClient, db: Session) -> None:
    """Module 1 opens without module 0 done (#214), and completing it, with module 0 never
    started, opens the last module: the warm-up isn't required for it."""
    _, m1_id, m2_id = _make_modules(db)
    _register_and_login(client, ALICE)

    res = client.get(f"/api/modules/{m1_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "open"
    assert (
        client.post(f"/api/modules/{m1_id}/position", json={"segmentPosition": 1}).status_code
        == 200
    )

    modules = client.get("/api/modules").json()
    assert [m["status"] for m in modules] == ["open", "complete", "open"]
    # The warm-up isn't recommended once a later module is done: the next one is.
    assert [m["recommended"] for m in modules] == [False, False, True]
    assert client.get(f"/api/modules/{m2_id}").status_code == 200


def test_completing_module_1_unlocks_module_2(client: TestClient, db: Session) -> None:
    """Cascading unlock: completing 0 → 1 opens, completing 1 → 2 opens."""
    m0_id, m1_id, _m2_id = _make_modules(db)
    _register_and_login(client, ALICE)

    client.post(f"/api/modules/{m0_id}/position", json={"segmentPosition": 1})
    client.post(f"/api/modules/{m1_id}/position", json={"segmentPosition": 1})

    modules = client.get("/api/modules").json()
    status_by_number = {m["number"]: m["status"] for m in modules}
    assert status_by_number[1] == "complete"
    assert status_by_number[2] == "open"


# ---------------------------------------------------------------------------
# 7. Progress is scoped per user
# ---------------------------------------------------------------------------


def test_user_b_sees_initial_locked_states_regardless_of_user_a_progress(
    client: TestClient, db: Session
) -> None:
    """User A completing module 0 must not affect User B's view."""
    m0_id, _, _ = _make_modules(db)

    # Alice registers and completes module 0.
    _register_and_login(client, ALICE)
    client.post(f"/api/modules/{m0_id}/position", json={"segmentPosition": 1})
    _logout(client)

    # Bob registers and checks his initial states.
    _register_and_login(client, BOB)
    modules = client.get("/api/modules").json()
    status_by_number = {m["number"]: m["status"] for m in modules}
    assert status_by_number[0] == "open"
    assert status_by_number[1] == "open"
    assert status_by_number[2] == "locked"  # Bob has NOT completed module 1


def test_user_a_position_does_not_bleed_into_user_b(client: TestClient, db: Session) -> None:
    """User A saving position 1 on module 0 must not appear on User B's detail view."""
    m0_id, _, _ = _make_modules(db)

    _register_and_login(client, ALICE)
    client.post(f"/api/modules/{m0_id}/position", json={"segmentPosition": 1})
    _logout(client)

    _register_and_login(client, BOB)
    detail = client.get(f"/api/modules/{m0_id}").json()
    assert detail["currentSegmentPosition"] == 0
    assert detail["status"] == "open"


# ---------------------------------------------------------------------------
# 8. Returning student sees saved position
# ---------------------------------------------------------------------------


def test_returning_student_sees_saved_current_segment_position(
    client: TestClient, db: Session
) -> None:
    """After saving position and logging back in, GET /api/modules/{id} returns the saved position."""
    m0_id, _, _ = _make_modules(db)
    _register_and_login(client, ALICE)

    # Save position 0 (in_progress, not the last segment).
    client.post(f"/api/modules/{m0_id}/position", json={"segmentPosition": 0})
    _logout(client)

    # Log back in.
    assert (
        client.post(
            "/api/auth/login", json={"email": ALICE["email"], "password": ALICE["password"]}
        ).status_code
        == 200
    )

    detail = client.get(f"/api/modules/{m0_id}").json()
    assert detail["currentSegmentPosition"] == 0
    assert detail["status"] == "in_progress"


def test_returning_student_sees_saved_position_on_list_endpoint(
    client: TestClient, db: Session
) -> None:
    """GET /api/modules also echoes the saved current_segment_position."""
    m0_id, _, _ = _make_modules(db)
    _register_and_login(client, ALICE)

    client.post(f"/api/modules/{m0_id}/position", json={"segmentPosition": 0})
    _logout(client)

    assert (
        client.post(
            "/api/auth/login", json={"email": ALICE["email"], "password": ALICE["password"]}
        ).status_code
        == 200
    )

    modules = client.get("/api/modules").json()
    m0 = next(m for m in modules if m["number"] == 0)
    assert m0["currentSegmentPosition"] == 0


# ---------------------------------------------------------------------------
# 9. Auth requirements (401 without a session)
# ---------------------------------------------------------------------------


def test_list_modules_requires_auth(client: TestClient, db: Session) -> None:
    _make_modules(db)
    # No registration / login — cookie jar is empty.
    assert client.get("/api/modules").status_code == 401


def test_get_module_detail_requires_auth(client: TestClient, db: Session) -> None:
    m0_id, _, _ = _make_modules(db)
    assert client.get(f"/api/modules/{m0_id}").status_code == 401


def test_post_position_requires_auth(client: TestClient, db: Session) -> None:
    m0_id, _, _ = _make_modules(db)
    assert (
        client.post(f"/api/modules/{m0_id}/position", json={"segmentPosition": 0}).status_code
        == 401
    )


# ---------------------------------------------------------------------------
# 10. POST /api/modules/{id}/position on locked / missing module
# ---------------------------------------------------------------------------


def test_post_position_on_locked_module_is_403(client: TestClient, db: Session) -> None:
    """Cannot save progress on a locked module."""
    _, _, m2_id = _make_modules(db)
    _register_and_login(client, ALICE)
    assert (
        client.post(f"/api/modules/{m2_id}/position", json={"segmentPosition": 0}).status_code
        == 403
    )


def test_post_position_on_missing_module_is_404(client: TestClient, db: Session) -> None:
    _make_modules(db)
    _register_and_login(client, ALICE)
    assert client.post("/api/modules/9999/position", json={"segmentPosition": 0}).status_code == 404


# ---------------------------------------------------------------------------
# 11. Input validation: negative segmentPosition is rejected at the API boundary
# ---------------------------------------------------------------------------


def test_post_position_with_negative_segment_position_is_422(
    client: TestClient, db: Session
) -> None:
    """A negative segmentPosition must be rejected with 422 Unprocessable Entity.

    Storing -1 in module_progress.current_segment_position would cause the ModulePage
    to access segments[-1] (undefined in JavaScript) on resume, crashing the render.
    The PositionIn schema's ``ge=0`` constraint prevents this at the API boundary.
    """
    m0_id, _, _ = _make_modules(db)
    _register_and_login(client, ALICE)

    res = client.post(f"/api/modules/{m0_id}/position", json={"segmentPosition": -1})
    assert res.status_code == 422


def test_a_module_with_no_segments_yet_doesnt_lock_the_ones_after_it(
    client: TestClient, db: Session
) -> None:
    """Content that hasn't been written yet can't be completed, so it mustn't block the course."""
    m0_id, m1_id, m2_id = _make_modules(db)
    db.execute(delete(Segment).where(Segment.module_id == m1_id))
    db.commit()
    _register_and_login(client, ALICE)
    client.post(f"/api/modules/{m0_id}/position", json={"segmentPosition": 1})

    statuses = {m["id"]: m["status"] for m in client.get("/api/modules").json()}
    assert statuses == {m0_id: "complete", m1_id: "open", m2_id: "open"}
    assert client.get(f"/api/modules/{m2_id}").status_code == 200


# ---------------------------------------------------------------------------
# 12. A segment must be done before moving past it (FR-2.7)
# ---------------------------------------------------------------------------


def _question(db: Session, activity_id: int) -> Activity:
    activity = Activity(
        id=activity_id,
        kind="multiple_choice",
        title=f"Question {activity_id}",
        config={
            "prompt": "Which?",
            "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        },
        solution={"correct": "a", "feedback": {}},
    )
    db.add(activity)
    return activity


def _make_gated_module(db: Session) -> int:
    """Module 0: a text segment, an activity, a video with one checkpoint, and a closing activity.
    Module 1 after it, so completion shows in what opens."""
    m0 = Module(id=0, slug="m0", title="Zero", goals=[], estimated_minutes=5, position=0)
    m1 = Module(id=1, slug="m1", title="One", goals=[], estimated_minutes=5, position=1)
    db.add_all([m0, m1])
    for activity_id in (1, 2, 3):
        _question(db, activity_id)
    db.flush()
    db.add_all(
        [
            Segment(id=1, module_id=0, position=0, kind="text", title="Read", body="Text."),
            Segment(id=2, module_id=0, position=1, kind="activity", title="Try", activity_id=1),
            Segment(id=3, module_id=0, position=2, kind="video", title="Watch"),
            Segment(id=4, module_id=0, position=3, kind="activity", title="Last", activity_id=3),
            Segment(id=5, module_id=1, position=0, kind="text", title="Next", body="Text."),
        ]
    )
    db.flush()
    video = Video(
        segment_id=3,
        title="BFS",
        media_path="/media/v.mp4",
        captions_path="/media/v.vtt",
        transcript="Words.",
        duration_seconds=60,
    )
    db.add(video)
    db.flush()
    db.add(Checkpoint(video_id=video.id, at_seconds=10, activity_id=2))
    db.commit()
    return m0.id


def _answer(client: TestClient, activity_id: int, option: str) -> None:
    res = client.post(
        f"/api/activities/{activity_id}/attempts", json={"submitted": {"selected": option}}
    )
    assert res.status_code in (200, 201), res.text


def _move(client: TestClient, position: int) -> int:
    return client.post("/api/modules/0/position", json={"segmentPosition": position}).status_code


def test_each_segment_says_whether_it_is_done(client: TestClient, db: Session) -> None:
    _make_gated_module(db)
    _register_and_login(client, ALICE)

    done = [s["done"] for s in client.get("/api/modules/0").json()["segments"]]
    assert done == [True, False, False, False]
    _answer(client, 1, "b")  # wrong, without the last hint: not done yet (#143)
    _answer(client, 2, "a")
    done = [s["done"] for s in client.get("/api/modules/0").json()["segments"]]
    assert done == [True, False, True, False]
    _answer(client, 1, "a")
    done = [s["done"] for s in client.get("/api/modules/0").json()["segments"]]
    assert done == [True, True, True, False]


def test_an_activity_must_be_answered_correctly_before_moving_on(
    client: TestClient, db: Session
) -> None:
    _make_gated_module(db)
    _register_and_login(client, ALICE)
    assert _move(client, 1) == 200  # past the text segment

    res = client.post("/api/modules/0/position", json={"segmentPosition": 2})
    assert res.status_code == 409
    assert "activity" in res.json()["detail"]
    assert client.get("/api/modules/0").json()["currentSegmentPosition"] == 1

    _answer(client, 1, "b")  # a wrong answer, without the last hint, isn't enough (#143)
    assert _move(client, 2) == 409
    _answer(client, 1, "a")
    assert _move(client, 2) == 200


def test_a_wrong_answer_after_the_last_hint_lets_the_student_move_on(
    client: TestClient, db: Session
) -> None:
    """The last hint gives the answer away: a student who needed it isn't kept on the segment."""
    _make_gated_module(db)
    db.add_all(Hint(activity_id=1, level=level, body=f"Hint {level}.") for level in (1, 2, 3, 4))
    db.commit()
    _register_and_login(client, ALICE)
    assert _move(client, 1) == 200

    for _ in range(3):
        assert client.post("/api/activities/1/hints").status_code == 201
    _answer(client, 1, "b")  # after hint 3: not yet
    assert _move(client, 2) == 409
    assert client.post("/api/activities/1/hints").status_code == 201  # hint 4, the last
    _answer(client, 1, "b")
    assert _move(client, 2) == 200


@pytest.mark.parametrize("purpose", ["mastery", "diagnostic"])
def test_one_real_answer_is_enough_for_a_mastery_or_diagnostic_item(
    client: TestClient, db: Session, purpose: str
) -> None:
    """Only the first answer counts on the mastery check (FR-7.1), and the diagnostic finds gaps
    rather than gating, so a wrong answer there moves the student on (#165 review)."""
    _make_gated_module(db)
    activity = db.get_one(Activity, 1)
    activity.purpose = purpose
    if purpose == "mastery":
        activity.objective_id = None
    db.commit()
    _register_and_login(client, ALICE)
    assert _move(client, 1) == 200

    _answer(client, 1, "b")  # wrong
    assert _move(client, 2) == 200


def test_a_wrong_practice_answer_still_does_not_move_the_student_on(
    client: TestClient, db: Session
) -> None:
    _make_gated_module(db)
    _register_and_login(client, ALICE)
    assert _move(client, 1) == 200
    _answer(client, 1, "b")
    assert _move(client, 2) == 409


def test_each_segment_says_whether_its_activity_was_attempted(
    client: TestClient, db: Session
) -> None:
    """The page opens a module at an activity passed without trying, never at one answered wrong
    (#165 review), so it needs to tell the two apart."""
    _make_gated_module(db)
    _register_and_login(client, ALICE)
    _answer(client, 1, "b")  # wrong: attempted, not done
    segments = client.get("/api/modules/0").json()["segments"]
    assert [(s["attempted"], s["done"]) for s in segments] == [
        (False, True),
        (True, False),
        (False, False),
        (False, False),
    ]


def test_a_blank_answer_is_refused_and_not_recorded(client: TestClient, db: Session) -> None:
    _make_gated_module(db)
    _register_and_login(client, ALICE)
    res = client.post("/api/activities/1/attempts", json={"submitted": {"selected": " "}})
    assert res.status_code == 422
    assert res.json()["detail"] == "Answer the activity before checking it."
    assert db.scalars(select(Attempt)).all() == []


def test_a_video_needs_every_checkpoint_passed(client: TestClient, db: Session) -> None:
    _make_gated_module(db)
    _register_and_login(client, ALICE)
    _answer(client, 1, "a")
    assert _move(client, 1) == 200
    assert _move(client, 2) == 200

    _answer(client, 2, "b")  # a wrong checkpoint answer doesn't pass it
    assert _move(client, 3) == 409
    _answer(client, 2, "a")
    assert _move(client, 3) == 200


def test_reaching_the_last_segment_completes_the_module_only_once_it_is_done(
    client: TestClient, db: Session
) -> None:
    _make_gated_module(db)
    _register_and_login(client, ALICE)
    _answer(client, 1, "a")
    _answer(client, 2, "a")
    for position in (1, 2, 3):
        assert _move(client, position) == 200
    assert client.get("/api/modules/0").json()["status"] == "in_progress"

    # "Finish module" before answering the last activity moves past nothing, so it isn't
    # refused, but the module isn't complete either.
    assert _move(client, 3) == 200
    assert client.get("/api/modules/0").json()["status"] == "in_progress"
    _answer(client, 3, "a")
    assert _move(client, 3) == 200  # "Finish module" once it is done completes the module
    statuses = {m["id"]: m["status"] for m in client.get("/api/modules").json()}
    assert statuses == {0: "complete", 1: "open"}


def test_back_then_forward_again_onto_an_unanswered_last_segment_is_not_refused(
    client: TestClient, db: Session
) -> None:
    """Reach the last segment, step back, then Next onto it again: saving a position already
    reached moves past nothing, so the student isn't stuck (the bug in review of #130)."""
    _make_gated_module(db)
    _register_and_login(client, ALICE)
    _answer(client, 1, "a")
    _answer(client, 2, "a")
    for position in (1, 2, 3):
        assert _move(client, position) == 200

    assert _move(client, 2) == 200  # Previous (the page doesn't save this, but it's harmless)
    assert _move(client, 3) == 200  # Next, back onto the last segment
    detail = client.get("/api/modules/0").json()
    assert (detail["currentSegmentPosition"], detail["status"]) == (3, "in_progress")


# A trace on A-B from A: BFS visits A, then B.
TRACE_CONFIG = {
    "directed": False,
    "vertices": ["A", "B"],
    "edges": [{"source": "A", "target": "B"}],
    "start_vertex": "A",
}


def _make_last_activity(db: Session, kind: str) -> None:
    activity = db.get_one(Activity, 3)
    activity.kind = kind
    if kind == "trace":
        activity.config, activity.solution = TRACE_CONFIG, {}
    db.commit()


def test_an_activity_kind_with_no_student_ui_yet_does_not_block(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mechanism stays for a kind added to the API before its screen: a kind in
    KINDS_WITHOUT_STUDENT_UI counts as done, so a module that ends on one can be finished
    without an attempt."""
    monkeypatch.setattr(modules_service, "KINDS_WITHOUT_STUDENT_UI", frozenset({"trace"}))
    _make_gated_module(db)
    _make_last_activity(db, "trace")
    _register_and_login(client, ALICE)
    _answer(client, 1, "a")
    _answer(client, 2, "a")

    done = [s["done"] for s in client.get("/api/modules/0").json()["segments"]]
    assert done == [True, True, True, True]
    for position in (1, 2, 3, 3):
        assert _move(client, position) == 200
    assert client.get("/api/modules/0").json()["status"] == "complete"


def test_a_supported_activity_kind_still_has_to_be_answered(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the kinds without a UI are let through: a multiple-choice activity still blocks."""
    monkeypatch.setattr(modules_service, "KINDS_WITHOUT_STUDENT_UI", frozenset({"trace"}))
    _make_gated_module(db)
    _make_last_activity(db, "trace")  # the last one; the first stays multiple choice
    _register_and_login(client, ALICE)
    assert _move(client, 1) == 200
    assert _move(client, 2) == 409


def test_every_activity_kind_now_has_a_student_screen() -> None:
    """#136: trace, fix the bug and choose tests have screens, so no kind is let through
    unanswered any more. The web's SUPPORTED list is the mirror (ActivityRenderer.tsx)."""
    assert not modules_service.KINDS_WITHOUT_STUDENT_UI


@pytest.mark.parametrize(
    ("kind", "config", "solution", "wrong"),
    [
        # A real but wrong trace (B can't leave first): fix/api-integrity refuses an empty one.
        (
            "trace",
            TRACE_CONFIG,
            {},
            {"rows": [{"visitedVertex": "B", "queue": [], "visited": ["B"], "order": ["B"]}]},
        ),
        (
            "fix_the_bug",
            {
                "prompt": "Fix it.",
                "lines": [{"id": 1, "text": "v = queue.pop()"}],
                "corrections": [{"id": 2, "text": "v = queue.popleft()"}],
            },
            {"order": [2]},
            {"order": [1]},
        ),
        (
            "choose_tests",
            {
                "prompt": "Which fail?",
                "code": "def bfs(graph, start): ...",
                "tests": [
                    {"id": "t1", "vertices": ["A"], "start_vertex": "A", "expected": ["A"]},
                    {"id": "t2", "vertices": ["B"], "start_vertex": "B", "expected": ["B"]},
                ],
            },
            {"exposing": ["t1"]},
            {"selected": ["t2"]},
        ),
    ],
)
def test_a_trace_fix_the_bug_or_choose_tests_segment_blocks_until_answered(
    client: TestClient,
    db: Session,
    kind: str,
    config: dict[str, Any],
    solution: dict[str, Any],
    wrong: dict[str, Any],
) -> None:
    """Regression for #136: on staging these kinds counted as done unanswered (so a student
    skipped module 3's trace practice without trying it). Now they gate like any other activity
    (FR-2.7): the module can't be finished until the student answers it correctly, or answers
    after its last hint (#143)."""
    _make_gated_module(db)
    activity = db.get_one(Activity, 3)
    activity.kind, activity.config, activity.solution = kind, config, solution
    db.add_all(Hint(activity_id=3, level=level, body=f"Hint {level}.") for level in (1, 2, 3, 4))
    db.commit()
    _register_and_login(client, ALICE)
    _answer(client, 1, "a")
    _answer(client, 2, "a")

    done = [s["done"] for s in client.get("/api/modules/0").json()["segments"]]
    assert done == [True, True, True, False]
    for position in (1, 2, 3):
        assert _move(client, position) == 200
    _move(client, 3)  # "Finish" on the unanswered last segment
    assert client.get("/api/modules/0").json()["status"] == "in_progress"

    res = client.post("/api/activities/3/attempts", json={"submitted": wrong})
    assert res.status_code == 201, res.text
    assert res.json()["correct"] is False
    # A wrong answer on its own isn't enough (#143)...
    assert [s["done"] for s in client.get("/api/modules/0").json()["segments"]][3] is False
    _move(client, 3)
    assert client.get("/api/modules/0").json()["status"] == "in_progress"
    # ...but one given after the last hint, which shows the answer, is.
    for _ in range(4):
        assert client.post("/api/activities/3/hints").status_code == 201
    assert client.post("/api/activities/3/attempts", json={"submitted": wrong}).status_code == 201
    assert [s["done"] for s in client.get("/api/modules/0").json()["segments"]][3] is True
    assert _move(client, 3) == 200
    assert client.get("/api/modules/0").json()["status"] == "complete"


def test_a_complete_module_can_be_stepped_through_freely(client: TestClient, db: Session) -> None:
    """Rereading never needs anything answered again, and never un-finishes the module."""
    _make_gated_module(db)
    _register_and_login(client, ALICE)
    for activity_id in (1, 2, 3):
        _answer(client, activity_id, "a")
    for position in (1, 2, 3, 3):
        assert _move(client, position) == 200
    assert _move(client, 0) == 200
    assert client.get("/api/modules/0").json()["status"] == "complete"


# ---------------------------------------------------------------------------
# 13. Completing a module: points, badge and event (FR-9.1, FR-9.3, FR-10.1, #141)
# ---------------------------------------------------------------------------


def _module_points(db: Session, module_id: int = 0) -> list[int]:
    return list(
        db.scalars(select(PointsEntry.points).where(PointsEntry.ref == f"module:{module_id}"))
    )


def _badges(client: TestClient) -> list[str]:
    return [b["badge"] for b in client.get("/api/rewards").json()["badges"]]


def test_completing_a_module_earns_its_points_and_badge_and_is_logged_once(
    client: TestClient, db: Session
) -> None:
    _make_gated_module(db)
    _register_and_login(client, ALICE)
    for activity_id in (1, 2, 3):
        _answer(client, activity_id, "a")
    for position in (1, 2, 3, 3):
        assert _move(client, position) == 200
    assert client.get("/api/modules/0").json()["status"] == "complete"

    assert _module_points(db) == [25]
    assert _badges(client) == ["first-module"]
    completed = db.scalars(select(Event).where(Event.type == "module_completed")).all()
    assert [e.ref for e in completed] == ["module:0"]

    # Rereading and finishing again changes nothing.
    assert _move(client, 0) == 200
    assert _move(client, 3) == 200
    assert _module_points(db) == [25]
    assert len(db.scalars(select(Event).where(Event.type == "module_completed")).all()) == 1


def test_a_module_clicked_through_with_hints_earns_no_points_until_real_work(
    client: TestClient, db: Session
) -> None:
    """Every hint opened, then a wrong answer: the module completes, but its points and badge need
    at least one right answer without hint 3 or 4 (FR-9.6; #166 review). One that comes later
    earns them then."""
    _make_gated_module(db)
    db.add_all(
        Hint(activity_id=a, level=level, body=f"Hint {level}.")
        for a in (1, 2, 3)
        for level in (1, 2, 3, 4)
    )
    db.commit()
    _register_and_login(client, ALICE)
    for activity_id in (1, 3):
        for _ in range(4):
            client.post(f"/api/activities/{activity_id}/hints")
        _answer(client, activity_id, "b")  # wrong, after the last hint: done (#143)
    for _ in range(4):
        client.post("/api/activities/2/hints")
    _answer(client, 2, "a")  # the checkpoint: right, but after hint 4
    for position in (1, 2, 3, 3):
        assert _move(client, position) == 200
    assert client.get("/api/modules/0").json()["status"] == "complete"
    assert _module_points(db) == []
    assert "first-module" not in _badges(client)

    # A right answer without heavy hints, later, in the complete module: now it's earned.
    hintless = Activity(
        id=4,
        kind="multiple_choice",
        title="Recall",
        module_id=0,
        purpose="retrieval",
        config={
            "prompt": "Which?",
            "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        },
        solution={"correct": "a", "feedback": {}},
    )
    db.add(hintless)
    db.commit()
    _answer(client, 4, "a")
    assert _module_points(db) == [25]
    assert "first-module" in _badges(client)


def test_the_seed_backfills_modules_completed_before_module_points(db: Session) -> None:
    """A module completed before module points existed earns them on the next seed, if earned,
    once (#166 review)."""
    _make_gated_module(db)
    user = User(email="ama@example.com", display_name="Ama", password_hash="x")  # noqa: S106
    db.add(user)
    db.flush()
    db.add(ModuleProgress(user_id=user.id, module_id=0, status="complete"))
    db.add(
        Attempt(user_id=user.id, activity_id=1, submitted={}, correct=True, score=1.0, detail={})
    )
    db.commit()

    assert backfill_module_rewards(db) == 1
    assert backfill_module_rewards(db) == 0  # safe to run on every seed
    db.commit()
    assert _module_points(db) == [25]
    badges = db.scalars(select(UserBadge.badge).where(UserBadge.user_id == user.id)).all()
    assert badges == ["first-module"]


def test_a_segment_in_a_locked_module_is_not_logged_as_viewed(
    client: TestClient, db: Session
) -> None:
    _make_gated_module(db)
    # A last module, locked until module 1 is complete (#214).
    db.add(Module(id=2, slug="m2", title="Two", goals=[], estimated_minutes=5, position=2))
    db.flush()
    db.add(Segment(id=6, module_id=2, position=0, kind="text", title="Last", body="Text."))
    db.commit()
    _register_and_login(client, ALICE)
    assert (
        client.post("/api/events", json={"type": "segment_viewed", "targetId": 6}).status_code
        == 204
    )
    assert (
        client.post("/api/events", json={"type": "segment_viewed", "targetId": 1}).status_code
        == 204
    )
    assert [e.ref for e in db.scalars(select(Event).where(Event.type == "segment_viewed"))] == [
        "segment:1"
    ]


def test_a_module_shortened_below_the_student_s_position_still_completes(
    client: TestClient, db: Session
) -> None:
    """Staff shorten a module (#128) after a student got further than its new end: the student
    opens it on its new last segment, and finishing it completes the module (#146)."""
    m0, _, _ = _make_modules(db)
    for position in (2, 3):
        db.add(Segment(module_id=m0, position=position, kind="text", title="More", body="More."))
    db.commit()
    _register_and_login(client, ALICE)
    for position in (1, 2):  # segment 2 of 0-3: in progress, not complete
        res = client.post(f"/api/modules/{m0}/position", json={"segmentPosition": position})
        assert res.status_code == 200
    db.execute(delete(Segment).where(Segment.module_id == m0, Segment.position >= 1))
    db.commit()

    detail = client.get(f"/api/modules/{m0}").json()
    assert detail["status"] == "in_progress"
    assert detail["currentSegmentPosition"] == 0  # clamped to the only segment left
    res = client.post(f"/api/modules/{m0}/position", json={"segmentPosition": 0})
    assert res.status_code == 200
    assert res.json()["status"] == "complete"
    assert client.get("/api/modules").json()[1]["status"] == "open"


def test_the_course_length_is_public_and_sums_every_module(client: TestClient, db: Session) -> None:
    """The register page and the map show the same length: every module's estimate (#146)."""
    _make_modules(db)
    res = client.get("/api/modules/length")  # nobody logged in
    assert res.status_code == 200
    assert res.json() == {"minutes": 5 + 12 + 10}
