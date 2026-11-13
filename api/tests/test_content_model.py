"""The course structure (#14, SE document §8): objectives, modules and their segments, and the tags
on activities (FR-4.3). The fixtures are checked as a whole, then loaded and re-loaded."""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Module, Objective, Segment, User, Video
from app.seed import load, read_fixtures


def write(folder: Path, data: dict[str, Any], name: str = "content.json") -> Path:
    (folder / name).write_text(json.dumps(data), encoding="utf-8")
    return folder


def objective(id: int = 1, **overrides: Any) -> dict[str, Any]:
    return {
        "id": id,
        "text": f"Objective {id}",
        "bloom_level": "Understand",
        "criterion": "At least 4 of 5 items correct.",
        "pass_fraction": 0.8,
        **overrides,
    }


def mcq(id: int = 1, **overrides: Any) -> dict[str, Any]:
    return {
        "id": id,
        "kind": "multiple_choice",
        "title": f"Question {id}",
        "config": {
            "prompt": "Q",
            "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        },
        "solution": {"correct": "a"},
        **overrides,
    }


def module(
    id: int = 0, segments: list[dict[str, Any]] | None = None, **overrides: Any
) -> dict[str, Any]:
    return {
        "id": id,
        "slug": f"module-{id}",
        "title": f"Module {id}",
        "goals": ["Do a thing."],
        "estimated_minutes": 5,
        "segments": segments if segments is not None else [],
        **overrides,
    }


def text(id: int, **overrides: Any) -> dict[str, Any]:
    return {
        "id": id,
        "kind": "text",
        "title": f"Text {id}",
        "body": "Some **Markdown**.",
        **overrides,
    }


def shows(id: int, activity_id: int) -> dict[str, Any]:
    return {"id": id, "kind": "activity", "title": f"Step {id}", "activity_id": activity_id}


def course(**overrides: Any) -> dict[str, Any]:
    """One objective, one module with a text and an activity segment, and its activity."""
    return {
        "objectives": [objective()],
        "modules": [module(segments=[text(1), shows(2, 1)])],
        "activities": [mcq(1, module_id=0, objective_id=1)],
        **overrides,
    }


# --- The committed fixtures ---------------------------------------------------------------------


def test_the_course_has_modules_0_to_6_and_objectives_1_to_8() -> None:
    content = read_fixtures()
    assert [m.id for m in sorted(content.modules, key=lambda m: m.id)] == list(range(7))
    assert sorted(o.id for o in content.objectives) == list(range(1, 9))
    # The ID document's Table 4 puts the whole course at about 75 minutes.
    assert 70 <= sum(m.estimated_minutes for m in content.modules) <= 80


def test_modules_0_3_and_6_have_enough_for_the_sprint_1_path() -> None:
    content = {m.id: m for m in read_fixtures().modules}
    for number in (0, 3, 6):
        assert content[number].segments, f"module {number} has no segments"
    activities = {a.id: a for a in read_fixtures().activities}
    # Module 0's refreshers are each ruled out by passing a diagnostic item (FR-8.1).
    refreshers = [s for s in content[0].segments if s.kind == "refresher"]
    assert refreshers
    for seg in refreshers:
        assert seg.skip_check_activity_id is not None
        assert activities[seg.skip_check_activity_id].purpose == "diagnostic"
    # Module 6 is the mastery check (FR-7.1).
    mastery = [a for a in activities.values() if a.module_id == 6 and a.purpose == "mastery"]
    assert mastery
    assert all(a.objective_id is not None for a in mastery)


# --- Content that can't work is refused, naming the problem -------------------------------------


@pytest.mark.parametrize(
    ("data", "problem"),
    [
        # Segments
        (course(modules=[module(segments=[shows(1, 99)])]), "no activity 99"),
        (
            course(modules=[module(segments=[{"id": 1, "kind": "activity", "title": "x"}])]),
            "needs an activity_id",
        ),
        (course(modules=[module(segments=[text(1, activity_id=1)])]), "only it has one"),
        (course(modules=[module(segments=[text(1, body="  ")])]), "needs a body"),
        (
            course(
                modules=[
                    module(segments=[{"id": 1, "kind": "refresher", "title": "x", "body": "y"}])
                ]
            ),
            "refresher_for",
        ),
        (course(modules=[module(segments=[text(1, refresher_for="queues")])]), "only a refresher"),
        (course(modules=[module(segments=[text(1, kind="quiz")])]), "kind"),
        (course(modules=[module(segments=[text(1), text(1)])]), "segment ids used twice"),
        (
            course(modules=[module(segments=[shows(1, 1), shows(2, 1)])]),
            "already shown by segment 1",
        ),
        (
            course(modules=[module(segments=[text(1, skip_check_activity_id=42)])]),
            "no activity 42",
        ),
        # Modules
        (course(modules=[module(0), module(0, slug="other")]), "module ids used twice"),
        (course(modules=[module(0), module(1, slug="module-0")]), "module slugs used twice"),
        (course(modules=[module(slug="Not A Slug")]), "pattern"),
        (course(modules=[module(goals=[])]), "goals"),
        (course(modules=[module(estimated_minutes=0)]), "estimated_minutes"),
        # Activities and their tags (FR-4.3)
        (course(activities=[mcq(1, module_id=5)]), "no module 5"),
        (course(activities=[mcq(1, objective_id=9)]), "no objective 9"),
        (course(activities=[mcq(1, purpose="homework")]), "purpose"),
        (course(activities=[mcq(1, purpose="mastery")]), "needs an objective_id"),
        (course(activities=[mcq(1, purpose="review")]), "needs an objective_id"),
        (course(activities=[mcq(1, purpose="diagnostic", objective_id=1)]), "has no objective"),
        (
            course(
                modules=[module(0, segments=[shows(1, 1)]), module(1, slug="m1")],
                activities=[mcq(1, module_id=1)],
            ),
            "belongs to module 1, not module 0",
        ),
        # Objectives
        (course(objectives=[objective(1), objective(1)]), "objective ids used twice"),
        (course(objectives=[objective(1, criterion="")]), "criterion"),
    ],
)
def test_content_that_cannot_work_is_refused(
    tmp_path: Path, data: dict[str, Any], problem: str
) -> None:
    with pytest.raises(ValueError, match=problem):
        read_fixtures(write(tmp_path, data))


def test_references_are_checked_across_files(tmp_path: Path) -> None:
    """Objectives, modules and activities may live in different files (one file per module)."""
    write(tmp_path, {"objectives": [objective()]}, "objectives.json")
    write(tmp_path, {"modules": [module(segments=[shows(1, 1)])]}, "module-0.json")
    write(tmp_path, {"activities": [mcq(1, module_id=0, objective_id=1)]}, "module-0-items.json")
    content = read_fixtures(tmp_path)
    assert [s.activity_id for s in content.modules[0].segments] == [1]


# --- Loading ---------------------------------------------------------------------------------------


def test_load_creates_the_course_structure(tmp_path: Path, db: Session) -> None:
    load(db, write(tmp_path, course()))
    db.expire_all()
    mod = db.get(Module, 0)
    assert mod is not None
    assert (mod.slug, mod.goals, mod.estimated_minutes, mod.position) == (
        "module-0",
        ["Do a thing."],
        5,
        0,
    )
    segments = db.scalars(select(Segment).order_by(Segment.position)).all()
    assert [(s.id, s.position, s.kind, s.activity_id) for s in segments] == [
        (1, 1, "text", None),
        (2, 2, "activity", 1),
    ]
    activity = db.get(Activity, 1)
    assert activity is not None
    assert (activity.module_id, activity.objective_id, activity.purpose) == (0, 1, "practice")
    assert db.get(Objective, 1).criterion == "At least 4 of 5 items correct."  # type: ignore[union-attr]


def test_a_rerun_reorders_and_removes_segments_without_touching_attempts_or_videos(
    tmp_path: Path, db: Session
) -> None:
    folder = write(tmp_path, course(modules=[module(segments=[text(1), shows(2, 1), text(3)])]))
    load(db, folder)
    user = User(email="ada@example.com", display_name="Ada", password_hash="not-a-real-hash")  # noqa: S106
    db.add(user)
    db.flush()
    db.add(
        Attempt(user_id=user.id, activity_id=1, submitted={}, correct=True, score=1.0, detail={})
    )
    video = Video(
        title="Lesson",
        media_path="/media/videos/a.mp4",
        captions_path="/media/videos/a.vtt",
        transcript="",
        duration_seconds=60,
        segment_id=3,
    )
    db.add(video)
    db.commit()

    # Segment 3 is dropped and the other two swap places.
    write(tmp_path, course(modules=[module(segments=[shows(2, 1), text(1, title="Moved")])]))
    load(db, folder)
    db.commit()
    db.expire_all()
    segments = db.scalars(select(Segment).order_by(Segment.position)).all()
    assert [(s.id, s.position, s.title) for s in segments] == [(2, 1, "Step 2"), (1, 2, "Moved")]
    assert db.get(Video, video.id).segment_id is None  # type: ignore[union-attr]  # kept, unplaced
    assert len(db.scalars(select(Attempt)).all()) == 1


def test_a_video_is_placed_in_one_segment_at_most(tmp_path: Path, db: Session) -> None:
    load(
        db,
        write(
            tmp_path,
            course(modules=[module(segments=[{"id": 1, "kind": "video", "title": "Watch"}])]),
        ),
    )
    for name in ("a", "b"):
        db.add(
            Video(
                title=name,
                media_path=f"/media/videos/{name}.mp4",
                captions_path=f"/media/videos/{name}.vtt",
                transcript="",
                duration_seconds=60,
                segment_id=1,
            )
        )
    with pytest.raises(Exception, match=r"(?i)unique"):
        db.flush()


def test_an_editor_made_activity_needs_no_module_or_objective(db: Session) -> None:
    """The staff video editor creates checkpoint activities outside the fixtures."""
    activity = Activity(
        kind="multiple_choice",
        title="Checkpoint",
        visible=True,
        config=mcq()["config"],
        solution=mcq()["solution"],
    )
    db.add(activity)
    db.flush()
    db.refresh(activity)
    assert (activity.module_id, activity.objective_id, activity.purpose) == (None, None, "practice")


def test_the_committed_course_loads(db: Session) -> None:
    load(db)
    db.commit()
    assert len(db.scalars(select(Module)).all()) == 7
    assert len(db.scalars(select(Objective)).all()) == 8
