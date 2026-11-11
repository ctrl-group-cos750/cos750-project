"""Support segments as content (FR-8.4, #172): the fixtures' `support_for`, its checks, the seed and
the staff editor. Putting support segments into a module must keep every student on the segment
they had reached: positions are numbers, so without that they would shift."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from support_fixture import (
    AFTER_SEGMENT,
    SUPPORT_ACTIVITY,
    SUPPORT_SEGMENTS,
    write_support_fixtures,
)

from app.models import (
    Activity,
    Attempt,
    ModuleProgress,
    Segment,
    ShownSegment,
    User,
)
from app.seed import load, read_fixtures
from app.services.modules import get_module_detail, get_modules_for_user, save_position

BASE = "/api/staff/content"
STAFF = {"email": "staff@example.com", "password": "Correct horse 1", "displayName": "Staff"}


def _edit(folder: Path, module: int, change: Any) -> Path:
    path = folder / f"module-{module}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")
    return folder


def _segments(data: dict[str, Any]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = data["modules"][0]["segments"]
    return segments


def test_the_test_support_group_is_valid(tmp_path: Path) -> None:
    content = read_fixtures(write_support_fixtures(tmp_path))
    module_2 = next(m for m in content.modules if m.id == 2)
    assert [s.id for s in module_2.segments if s.support_for == 6] == list(SUPPORT_SEGMENTS)


def _module_6_support(data: dict[str, Any]) -> None:
    _segments(data).append({"id": 699, "kind": "text", "title": "x", "body": "x", "support_for": 1})


def _video_support(data: dict[str, Any]) -> None:
    segments = _segments(data)
    at = next(i for i, s in enumerate(segments) if s["id"] == SUPPORT_SEGMENTS[1])
    segments[at] = {"id": SUPPORT_SEGMENTS[1], "kind": "video", "title": "x", "support_for": 6}


def _support_activity(**changes: Any) -> Any:
    def change(data: dict[str, Any]) -> None:
        next(a for a in data["activities"] if a["id"] == SUPPORT_ACTIVITY).update(changes)

    return change


def _support_first(data: dict[str, Any]) -> None:
    segments = _segments(data)
    support = [s for s in segments if s.get("support_for")]
    data["modules"][0]["segments"] = support + [s for s in segments if not s.get("support_for")]


def _support_for(objective: int) -> Any:
    def change(data: dict[str, Any]) -> None:
        for s in _segments(data):
            if s.get("support_for"):
                s["support_for"] = objective

    return change


def _skippable(data: dict[str, Any]) -> None:
    support = next(s for s in _segments(data) if s["id"] == SUPPORT_SEGMENTS[0])
    support["skip_check_activity_id"] = SUPPORT_ACTIVITY


@pytest.mark.parametrize(
    ("module", "change", "problem"),
    [
        (6, _module_6_support, "mastery check"),
        (2, _video_support, "not a video"),
        (2, _support_activity(purpose="review"), "practice item on objective 6"),
        (2, _support_activity(objective_id=5), "practice item on objective 6"),
        (2, _support_first, "earlier in module 2"),
        (2, _support_for(1), "earlier in module 2"),  # module 2 has no practice on objective 1
        (2, _support_for(9), "less than or equal to 8"),
        (2, _support_for("six"), "valid integer"),
        (2, _skippable, "can't be skipped"),
    ],
)
def test_misplaced_support_is_refused(
    tmp_path: Path, module: int, change: Any, problem: str
) -> None:
    folder = _edit(write_support_fixtures(tmp_path), module, change)
    with pytest.raises(ValueError, match=problem):
        read_fixtures(folder)


def test_support_for_an_objective_that_doesnt_exist_is_refused(tmp_path: Path) -> None:
    folder = write_support_fixtures(tmp_path)
    path = folder / "objectives.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["objectives"] = [o for o in data["objectives"] if o["id"] != 6]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="objective"):
        read_fixtures(folder)


def test_a_review_path_has_no_support(tmp_path: Path) -> None:
    folder = write_support_fixtures(tmp_path)
    path = folder / "review.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["review_paths"][0]["segments"][0]["support_for"] = data["review_paths"][0]["objective_id"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="corrective step"):
        read_fixtures(folder)


# --- The upgrade: support put into a module students are part-way through ----------------------


def _student(db: Session, email: str) -> int:
    user = User(email=email, display_name=email, password_hash="x")  # noqa: S106 (test only)
    db.add(user)
    db.commit()
    return user.id


def _at(db: Session, user_id: int, segment_id: int, status: str = "in_progress") -> None:
    ids = [
        s.id
        for s in db.scalars(
            select(Segment).where(Segment.module_id == 2).order_by(Segment.position)
        )
    ]
    db.add(
        ModuleProgress(
            user_id=user_id,
            module_id=2,
            status=status,
            current_segment_position=ids.index(segment_id),
        )
    )
    for module_id in (0, 1):
        db.add(ModuleProgress(user_id=user_id, module_id=module_id, status="complete"))
    recall = select(Activity.id).where(Activity.module_id == 2, Activity.purpose == "retrieval")
    for activity_id in db.scalars(recall).all():
        db.add(
            Attempt(
                user_id=user_id,
                activity_id=activity_id,
                submitted={},
                correct=True,
                score=1.0,
                detail={},
            )
        )
    db.commit()


def _attempt(db: Session, user_id: int, activity_id: int, correct: bool) -> None:
    db.add(
        Attempt(
            user_id=user_id,
            activity_id=activity_id,
            submitted={},
            correct=correct,
            score=float(correct),
            detail={},
        )
    )
    db.commit()


def _on(db: Session, user_id: int) -> int:
    """The id of the segment the student has reached in module 2."""
    db.expire_all()
    row = db.scalars(
        select(ModuleProgress).where(
            ModuleProgress.user_id == user_id, ModuleProgress.module_id == 2
        )
    ).one()
    ordered = db.scalars(
        select(Segment.id).where(Segment.module_id == 2).order_by(Segment.position)
    ).all()
    return ordered[row.current_segment_position]


def _shown(db: Session, user_id: int) -> dict[int, bool]:
    detail = get_module_detail(db, user_id, 2)
    return {s.id: s.shown for s in detail.segments}


def test_students_part_way_keep_their_place_when_support_is_put_in(
    tmp_path: Path, db: Session
) -> None:
    load(db)  # staging's content
    struggling_before = _student(db, "a@example.com")  # wrong twice, not yet at the support
    _at(db, struggling_before, 207)
    _attempt(db, struggling_before, 206, False)
    _attempt(db, struggling_before, 207, False)
    struggling_past = _student(db, "b@example.com")  # wrong twice, already past it
    _at(db, struggling_past, 209)
    for activity_id in (206, 207, 208):
        _attempt(db, struggling_past, activity_id, False)
    confident = _student(db, "c@example.com")  # right every time, on the last base item
    _at(db, confident, AFTER_SEGMENT)
    for activity_id in (206, 207, 208):
        _attempt(db, confident, activity_id, True)
    finished = _student(db, "d@example.com")
    _at(db, finished, 209, status="complete")
    attempts = db.scalar(select(func.count(Attempt.id)))

    folder = write_support_fixtures(tmp_path / "with-support")
    for _ in range(2):  # the API container seeds on every start
        load(db, folder)

    # Everyone is on the same segment as before, though its number moved for some.
    assert _on(db, struggling_before) == 207
    assert _on(db, struggling_past) == 209
    assert _on(db, confident) == AFTER_SEGMENT
    assert _on(db, finished) == 209
    assert db.scalar(select(func.count(Attempt.id))) == attempts
    statuses = {
        u: next(m.status for m in get_modules_for_user(db, u) if m.id == 2)
        for u in (struggling_before, struggling_past, confident, finished)
    }
    assert statuses == {
        struggling_before: "in_progress",
        struggling_past: "in_progress",
        confident: "in_progress",
        finished: "complete",
    }
    # Only the student who is struggling and hasn't got there yet sees the support.
    assert all(_shown(db, struggling_before)[s] for s in SUPPORT_SEGMENTS)
    for user_id in (struggling_past, confident, finished):
        assert not any(_shown(db, user_id)[s] for s in SUPPORT_SEGMENTS)
    # The confident student moves on from the last base item straight to 209.
    detail = get_module_detail(db, confident, 2)
    after = [s.id for s in detail.segments].index(209)
    save_position(db, confident, 2, after)
    db.commit()
    assert _on(db, confident) == 209

    # Taking the support out again (or staff removing it) keeps places too, and its records go.
    save_position(db, struggling_before, 2, [s.id for s in detail.segments].index(208))
    db.commit()
    assert db.scalar(select(func.count(ShownSegment.id))) == 2
    load(db)
    assert _on(db, struggling_before) == 208
    assert _on(db, struggling_past) == 209
    assert _on(db, finished) == 209
    assert db.scalar(select(func.count(ShownSegment.id))) == 0


def test_a_student_on_a_removed_segment_goes_to_the_one_before(tmp_path: Path, db: Session) -> None:
    load(db)
    user_id = _student(db, "a@example.com")
    _at(db, user_id, 207)
    folder = _edit(
        write_support_fixtures(tmp_path),
        2,
        lambda data: data["modules"][0].update(
            segments=[s for s in _segments(data) if s["id"] != 207]
        ),
    )
    load(db, folder)
    assert _on(db, user_id) == 206


# --- The staff editor ---------------------------------------------------------------------------


@pytest.fixture
def staff(client: TestClient, db: Session) -> TestClient:
    load(db)
    assert client.post("/api/auth/register", json=STAFF).status_code == 201
    user = db.scalars(select(User).where(User.email == STAFF["email"])).one()
    user.is_staff = True
    db.commit()
    return client


def _module(client: TestClient, module_id: int) -> dict[str, Any]:
    data: dict[str, Any] = client.get(f"{BASE}/modules/{module_id}").json()
    for key in ("id", "edited", "inRepository", "segmentsEdited"):
        data.pop(key)
    return data


def _new_support_question(db: Session) -> None:
    db.add(
        Activity(
            id=SUPPORT_ACTIVITY,
            kind="multiple_choice",
            title="Both ways",
            module_id=2,
            objective_id=6,
            purpose="practice",
            config={
                "prompt": "?",
                "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            },
            solution={"correct": "a"},
        )
    )
    db.commit()


def test_staff_can_add_support_and_students_keep_their_place(
    staff: TestClient, db: Session
) -> None:
    _new_support_question(db)
    learner = _student(db, "a@example.com")
    _at(db, learner, 209)
    body = _module(staff, 2)
    at = next(i for i, s in enumerate(body["segments"]) if s["id"] == AFTER_SEGMENT) + 1
    body["segments"][at:at] = [
        {"kind": "worked_example", "title": "Another way", "body": "Example.", "supportFor": 6},
        {"kind": "activity", "title": "Try again", "activityId": SUPPORT_ACTIVITY, "supportFor": 6},
    ]
    saved = staff.put(f"{BASE}/modules/2", json=body)
    assert saved.status_code == 200, saved.text
    assert [s["supportFor"] for s in saved.json()["segments"]][at : at + 2] == [6, 6]
    assert _on(db, learner) == 209  # moved down two places, onto the same segment


def test_staff_cant_put_support_in_the_mastery_check(staff: TestClient) -> None:
    body = _module(staff, 6)
    body["segments"].append({"kind": "text", "title": "x", "body": "x", "supportFor": 1})
    refused = staff.put(f"{BASE}/modules/6", json=body)
    assert refused.status_code == 422
    assert "mastery check" in refused.json()["detail"]


def test_staff_cant_put_support_on_a_review_path(staff: TestClient) -> None:
    path = staff.get(f"{BASE}/review-paths/1").json()
    path["segments"][0]["supportFor"] = 1
    refused = staff.put(f"{BASE}/review-paths/1", json={"segments": path["segments"]})
    assert refused.status_code == 422
    assert "corrective step" in refused.json()["detail"]


def test_staff_cant_point_support_at_a_mismatched_question(staff: TestClient) -> None:
    body = _module(staff, 2)
    # Segment 205's activity is practice on objective 2, so it can't be support for objective 6.
    moved = next(s for s in body["segments"] if s["id"] == 205)
    body["segments"].remove(moved)
    body["segments"].append(moved | {"supportFor": 6})
    refused = staff.put(f"{BASE}/modules/2", json=body)
    assert refused.status_code == 422
    assert "practice item on objective 6" in refused.json()["detail"]
