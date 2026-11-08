"""The content fixtures and their loader (app/seed). The first test is the CI gate the SE
document asks for (NFR-M5): an invalid fixture fails the build."""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Activity,
    Attempt,
    Checkpoint,
    GraphScenario,
    Hint,
    Segment,
    User,
    Video,
)
from app.seed import EDITOR_IDS_FROM, load, move_editor_activities, read_fixtures
from app.services.mastery import counts


def test_every_committed_fixture_is_valid() -> None:
    read_fixtures()  # raises, naming the file, if any fixture is invalid


def write(folder: Path, data: dict[str, Any]) -> Path:
    (folder / "content.json").write_text(json.dumps(data), encoding="utf-8")
    return folder


def activity(**overrides: Any) -> dict[str, Any]:
    return {
        "id": 1,
        "kind": "multiple_choice",
        "title": "Q",
        "config": {
            "prompt": "Q",
            "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        },
        "solution": {"correct": "a"},
        "hints": [{"level": 1, "body": "one"}, {"level": 2, "body": "two"}],
        **overrides,
    }


def graph(**overrides: Any) -> dict[str, Any]:
    return {
        "id": 1,
        "name": "Line",
        "vertices": ["A", "B", "C"],
        "edges": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}],
        "start_vertex": "A",
        **overrides,
    }


def trace_activity(**overrides: Any) -> dict[str, Any]:
    """A trace activity: the graph lives in `config`, the solution is empty (the engine derives
    the traversal, FR-6.6)."""
    base = {
        "directed": False,
        "vertices": ["A", "B", "C"],
        "edges": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}],
        "start_vertex": "A",
    }
    return activity(kind="trace", config=base, solution={}) | overrides


@pytest.mark.parametrize(
    ("data", "problem"),
    [
        ({"activities": [activity(solution={"correct": "z"})]}, "not one of the options"),
        ({"activities": [activity(solution={"correct": "a", "feedback": {"q": "x"}})]}, "unknown"),
        ({"activities": [activity(kind="essay")]}, "kind"),
        ({"activities": [activity(config={"prompt": "Q", "options": []})]}, "options"),
        (
            {
                "activities": [
                    activity(hints=[{"level": 1, "body": "a"}, {"level": 1, "body": "b"}])
                ]
            },
            "share a level",
        ),
        ({"activities": [activity(hints=[{"level": 5, "body": "a"}])]}, "level"),
        ({"activities": [activity(), activity()]}, "used twice"),
        ({"activities": [activity(extra="x")]}, "extra"),
        ({"videos": []}, "videos"),  # videos are made in the editor, not in fixtures
        ({"graphs": [graph(start_vertex="Z")]}, "start vertex"),
        ({"graphs": [graph(vertices=["A", "B", "A"])]}, "same vertex"),
        ({"graphs": [graph(edges=[{"source": "A", "target": "Z"}])]}, "not in the graph"),
        ({"graphs": [graph(vertices=["A", ""])]}, "pattern"),
        ({"graphs": [graph(vertices=[])]}, "vertices"),
        ({"graphs": [graph(), graph()]}, "graph ids used twice"),
        ({"graphs": [graph(weight=2)]}, "extra"),
        # Trace activities: the graph in config is run through the engine at load (FR-6.6).
        (
            {
                "activities": [
                    trace_activity(config={**trace_activity()["config"], "start_vertex": "Z"})
                ]
            },
            "start vertex",
        ),
        (
            {"activities": [trace_activity(solution={"order": ["A"]})]},
            "extra",
        ),  # trace keeps no solution
    ],
)
def test_invalid_fixtures_are_refused(tmp_path: Path, data: dict[str, Any], problem: str) -> None:
    with pytest.raises(ValueError, match=problem):
        read_fixtures(write(tmp_path, data))


def test_a_valid_trace_activity_loads(tmp_path: Path) -> None:
    read_fixtures(write(tmp_path, {"activities": [trace_activity()]}))  # must not raise


def test_load_creates_content_and_a_rerun_updates_it_without_touching_attempts(
    tmp_path: Path, db: Session
) -> None:
    folder = write(tmp_path, {"activities": [activity()]})
    load(db, folder)
    user = User(email="ada@example.com", display_name="Ada", password_hash="not-a-real-hash")  # noqa: S106
    db.add(user)
    db.flush()
    db.add(
        Attempt(user_id=user.id, activity_id=1, submitted={}, correct=True, score=1.0, detail={})
    )
    db.commit()

    write(tmp_path, {"activities": [activity(title="Q2", hints=[{"level": 1, "body": "new"}])]})
    load(db, folder)
    db.expire_all()
    assert db.get(Activity, 1).title == "Q2"  # type: ignore[union-attr]
    assert [h.body for h in db.scalars(select(Hint))] == ["new"]
    assert len(db.scalars(select(Attempt)).all()) == 1


def test_a_bad_fixture_writes_nothing(tmp_path: Path, db: Session) -> None:
    folder = write(tmp_path, {"activities": [activity(kind="essay")]})
    with pytest.raises(ValueError, match="kind"):
        load(db, folder)
    assert db.scalars(select(Activity)).all() == []


def test_load_creates_graphs_the_api_can_run_and_a_rerun_updates_them(
    tmp_path: Path, db: Session
) -> None:
    folder = write(tmp_path, {"graphs": [graph()]})
    load(db, folder)
    write(tmp_path, {"graphs": [graph(name="Line again", directed=True)]})
    load(db, folder)
    db.expire_all()
    scenario = db.get(GraphScenario, 1)
    assert scenario is not None
    assert (scenario.name, scenario.directed) == ("Line again", True)
    assert scenario.edges == [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}]
    assert len(db.scalars(select(GraphScenario)).all()) == 1


# --- Fixture ids and the video editor's questions share the activities table ------------------


def editor_question(db: Session, activity_id: int, prompt: str) -> Checkpoint:
    """A checkpoint question as the video editor makes it, with a hint and a student's attempt."""
    db.add(
        Activity(
            id=activity_id,
            kind="multiple_choice",
            title=f"Video at 0:{activity_id:02d}",
            visible=True,
            config={"prompt": prompt, "options": [{"id": "a", "label": "A"}]},
            solution={"correct": "a"},
        )
    )
    video = db.scalar(select(Video)) or Video(
        title="BFS",
        media_path="/media/bfs.mp4",
        captions_path="/media/bfs.vtt",
        transcript="",
        duration_seconds=60,
    )
    db.add(video)
    db.flush()
    checkpoint = Checkpoint(video_id=video.id, at_seconds=activity_id, activity_id=activity_id)
    user = db.scalar(select(User)) or User(
        email="ada@example.com",
        display_name="Ada",
        password_hash="not-a-real-hash",  # noqa: S106
    )
    db.add_all([checkpoint, user])
    db.flush()
    db.add(Hint(activity_id=activity_id, level=1, body=f"hint for {prompt}"))
    db.add(
        Attempt(
            user_id=user.id,
            activity_id=activity_id,
            submitted={},
            correct=True,
            score=1.0,
            detail={},
        )
    )
    db.commit()
    return checkpoint


def test_a_fixture_never_overwrites_a_video_editor_question(tmp_path: Path, db: Session) -> None:
    checkpoint = editor_question(db, 1, "Editor question")

    load(db, write(tmp_path, {"activities": [activity(id=1, title="Fixture")]}))
    db.expire_all()

    assert db.get(Activity, 1).title == "Fixture"  # type: ignore[union-attr]
    moved = db.get(Activity, EDITOR_IDS_FROM + 1)
    assert moved is not None
    assert moved.config["prompt"] == "Editor question"
    assert db.get(Checkpoint, checkpoint.id).activity_id == moved.id  # type: ignore[union-attr]
    assert [h.body for h in db.scalars(select(Hint).where(Hint.activity_id == moved.id))] == [
        "hint for Editor question"
    ]
    assert db.scalars(select(Attempt.activity_id)).all() == [moved.id]


def test_moving_editor_questions_happens_once(tmp_path: Path, db: Session) -> None:
    editor_question(db, 3, "Third")
    folder = write(tmp_path, {"activities": [activity(id=1)]})
    load(db, folder)
    load(db, folder)
    db.expire_all()

    assert db.get(Activity, 3) is None
    assert db.get(Activity, EDITOR_IDS_FROM + 3) is not None
    assert move_editor_activities(db) == []


def test_a_question_already_overwritten_by_a_module_fixture_is_moved_and_the_fixture_kept(
    tmp_path: Path, db: Session
) -> None:
    # Staging on 8 Nov: the first deploy with fixtures wrote module 0's activity 1 over the
    # editor's question 1, so the checkpoint and module 0's segment both point at activity 1.
    folder = write(
        tmp_path,
        {
            "modules": [
                {
                    "id": 0,
                    "slug": "warm-up",
                    "title": "Warm-up",
                    "estimated_minutes": 5,
                    "goals": ["Use a queue."],
                    "segments": [{"id": 1, "kind": "activity", "title": "Q", "activity_id": 1}],
                }
            ],
            "activities": [activity(id=1, title="Fixture", module_id=0)],
        },
    )
    load(db, folder)
    video = Video(
        title="BFS", media_path="/m.mp4", captions_path="/m.vtt", transcript="", duration_seconds=6
    )
    db.add(video)
    db.flush()
    checkpoint = Checkpoint(video_id=video.id, at_seconds=1, activity_id=1)
    db.add(checkpoint)
    db.commit()

    load(db, folder)
    db.expire_all()

    assert db.get(Checkpoint, checkpoint.id).activity_id == EDITOR_IDS_FROM + 1  # type: ignore[union-attr]
    assert db.get(Activity, 1).title == "Fixture"  # type: ignore[union-attr]
    assert db.get(Segment, 1).activity_id == 1  # type: ignore[union-attr]


def test_a_fixture_cannot_use_the_editors_ids(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="video editor"):
        read_fixtures(write(tmp_path, {"activities": [activity(id=EDITOR_IDS_FROM)]}))


# --- An activity the fixtures stop listing ---------------------------------------------------


def test_an_activity_the_fixtures_drop_is_deleted_if_nobody_used_it(
    tmp_path: Path, db: Session
) -> None:
    load(db, write(tmp_path, {"activities": [activity(id=1), activity(id=2)]}))
    load(db, write(tmp_path, {"activities": [activity(id=2)]}))
    db.expire_all()

    assert db.get(Activity, 1) is None
    assert db.scalars(select(Hint.activity_id).distinct()).all() == [2]


def test_a_dropped_activity_someone_answered_is_kept_but_hidden_and_no_longer_a_mastery_item(
    tmp_path: Path, db: Session
) -> None:
    # An old placeholder mastery item a later fixture replaced, which a student had answered.
    db.add(
        Activity(
            id=1,
            kind="multiple_choice",
            title="Old placeholder",
            visible=True,
            purpose="mastery",
            config={"prompt": "Q", "options": []},
            solution={"correct": "a"},
        )
    )
    user = User(email="ada@example.com", display_name="Ada", password_hash="not-a-real-hash")  # noqa: S106
    db.add(user)
    db.flush()
    db.add(
        Attempt(user_id=user.id, activity_id=1, submitted={}, correct=True, score=1.0, detail={})
    )
    db.commit()
    assert counts(db.get_one(Activity, 1))

    load(db, write(tmp_path, {"activities": [activity(id=2)]}))
    db.expire_all()

    kept = db.get_one(Activity, 1)
    assert (kept.visible, kept.purpose, kept.module_id) == (False, "practice", None)
    assert len(db.scalars(select(Attempt)).all()) == 1
    assert not counts(kept)


def test_dropping_fixtures_never_touches_a_video_editor_question(
    tmp_path: Path, db: Session
) -> None:
    editor_question(db, EDITOR_IDS_FROM + 5, "Editor question")
    load(db, write(tmp_path, {"activities": [activity(id=1)]}))
    db.expire_all()

    assert db.get(Activity, EDITOR_IDS_FROM + 5) is not None
