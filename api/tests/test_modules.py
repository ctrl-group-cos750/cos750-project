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
from sqlalchemy.orm import Session

from app.models import Module, Segment

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALICE = {"email": "alice@example.com", "password": "Correct horse 1", "displayName": "Alice"}
BOB = {"email": "bob@example.com", "password": "Correct horse 2", "displayName": "Bob"}


def _make_modules(db: Session) -> tuple[int, int, int]:
    """Insert 3 modules (numbers 0-2), each with 2 segments.

    Returns the three module IDs in order.
    """
    m0 = Module(
        number=0, slug="warm-up", title="Warm-up", goals="Goal 0.", estimated_minutes=5, position=0
    )
    m1 = Module(
        number=1,
        slug="graphs",
        title="Graphs",
        goals="Goal 1.",
        estimated_minutes=12,
        position=1,
    )
    m2 = Module(
        number=2,
        slug="python-graphs",
        title="A graph in Python",
        goals="Goal 2.",
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

    assert body["goals"] == "Goal 0."
    segs = body["segments"]
    assert len(segs) == 2
    # Segments come back in position order.
    assert [s["position"] for s in segs] == [0, 1]
    assert segs[0]["kind"] == "text"
    assert segs[1]["kind"] == "worked_example"


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


def test_exceeding_last_segment_position_still_completes(client: TestClient, db: Session) -> None:
    """segmentPosition >= last_index should mark complete (>= not just ==)."""
    m0_id, _, _ = _make_modules(db)
    _register_and_login(client, ALICE)

    res = client.post(f"/api/modules/{m0_id}/position", json={"segmentPosition": 5})
    assert res.json()["status"] == "complete"


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
