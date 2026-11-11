"""End-to-end tests for the module-map and progress endpoints (FR-2).

GET  /api/modules                      → list[ModuleOut]
GET  /api/modules/{id}                 → ModuleDetailOut  (404 missing, 403 locked)
POST /api/modules/{id}/position        → ModuleDetailOut  (commits progress)

Seeding strategy: insert Module + Segment rows directly in the test db session — the
same approach test_seed.py uses when it inserts Module/ModuleProgress/User rows directly.
Using 3 modules (numbers 0, 1, 2) with 2 segments each is enough to exercise the full
unlock chain and the completion logic while keeping the setup minimal.
"""

from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Checkpoint, Module, Objective, Segment, Video
from app.services.mastery import counts

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
    """Module 0 is open; modules 1 and 2 are locked for a brand-new student."""
    _make_modules(db)
    _register_and_login(client, ALICE)

    res = client.get("/api/modules")
    assert res.status_code == 200
    modules = res.json()
    assert len(modules) == 3  # 3 modules were seeded

    # Returned in position order.
    assert [m["number"] for m in modules] == [0, 1, 2]

    # Status — module 0 open, rest locked (no progress yet).
    assert modules[0]["status"] == "open"
    assert modules[1]["status"] == "locked"
    assert modules[2]["status"] == "locked"


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
    """Module 1 is locked until module 0 is complete — should return 403."""
    _, m1_id, _ = _make_modules(db)
    _register_and_login(client, ALICE)

    res = client.get(f"/api/modules/{m1_id}")
    assert res.status_code == 403


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


def test_completing_module_0_lets_student_access_module_1_detail(
    client: TestClient, db: Session
) -> None:
    """After module 0 is complete, GET /api/modules/{m1_id} returns 200 (no longer 403)."""
    m0_id, m1_id, _ = _make_modules(db)
    _register_and_login(client, ALICE)

    # Locked before.
    assert client.get(f"/api/modules/{m1_id}").status_code == 403

    # Complete module 0.
    client.post(f"/api/modules/{m0_id}/position", json={"segmentPosition": 1})

    # Unlocked now.
    res = client.get(f"/api/modules/{m1_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "open"


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
    assert status_by_number[1] == "locked"  # Bob has NOT completed module 0
    assert status_by_number[2] == "locked"


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
    _, m1_id, _ = _make_modules(db)
    _register_and_login(client, ALICE)
    assert (
        client.post(f"/api/modules/{m1_id}/position", json={"segmentPosition": 0}).status_code
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
    _answer(client, 1, "b")
    _answer(client, 2, "a")
    done = [s["done"] for s in client.get("/api/modules/0").json()["segments"]]
    assert done == [True, True, True, False]


def test_an_activity_must_be_answered_once_right_or_wrong_before_moving_on(
    client: TestClient, db: Session
) -> None:
    _make_gated_module(db)
    _register_and_login(client, ALICE)
    assert _move(client, 1) == 200  # past the text segment

    res = client.post("/api/modules/0/position", json={"segmentPosition": 2})
    assert res.status_code == 409
    assert "activity" in res.json()["detail"]
    assert client.get("/api/modules/0").json()["currentSegmentPosition"] == 1

    _answer(client, 1, "b")  # wrong is enough: it is practice
    assert _move(client, 2) == 200


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
    _answer(client, 3, "b")
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


def test_an_activity_kind_with_no_student_ui_yet_does_not_block(
    client: TestClient, db: Session
) -> None:
    """A trace activity can't be answered in the web yet, so it counts as done: a module that
    ends on one can be finished without an attempt (KINDS_WITHOUT_STUDENT_UI)."""
    _make_gated_module(db)
    db.get_one(Activity, 3).kind = "trace"
    db.commit()
    _register_and_login(client, ALICE)
    _answer(client, 1, "a")
    _answer(client, 2, "a")

    done = [s["done"] for s in client.get("/api/modules/0").json()["segments"]]
    assert done == [True, True, True, True]
    for position in (1, 2, 3, 3):
        assert _move(client, position) == 200
    assert client.get("/api/modules/0").json()["status"] == "complete"


def test_a_supported_activity_kind_still_has_to_be_answered(
    client: TestClient, db: Session
) -> None:
    """Only the kinds without a UI are let through: a multiple-choice activity still blocks."""
    _make_gated_module(db)
    db.get_one(Activity, 3).kind = "trace"  # the last one; the first stays multiple choice
    db.commit()
    _register_and_login(client, ALICE)
    assert _move(client, 1) == 200
    assert _move(client, 2) == 409


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
