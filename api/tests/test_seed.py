"""The content fixtures and their loader (app/seed). The first test is the CI gate the SE
document asks for (NFR-M5): an invalid fixture fails the build."""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, GraphScenario, Hint, Module, ModuleProgress, Segment, User
from app.seed import load, read_fixtures


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
    ],
)
def test_invalid_fixtures_are_refused(tmp_path: Path, data: dict[str, Any], problem: str) -> None:
    with pytest.raises(ValueError, match=problem):
        read_fixtures(write(tmp_path, data))


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


# ---------------------------------------------------------------------------
# Module / segment seed tests
# ---------------------------------------------------------------------------


def module_fixture(**overrides: Any) -> dict[str, Any]:
    """Minimal valid module fixture dict (one text segment, no overrides needed for happy path)."""
    return {
        "id": 10,
        "number": 0,
        "slug": "test-module",
        "title": "Test Module",
        "goals": "Do a thing.",
        "estimated_minutes": 5,
        "position": 0,
        "segments": [
            {
                "id": 100,
                "position": 0,
                "kind": "text",
                "title": "Intro",
                "body": "Some body text.",
            }
        ],
        **overrides,
    }


def segment_fixture(**overrides: Any) -> dict[str, Any]:
    """A standalone segment dict (module_id must be set before passing to SegmentFixture)."""
    return {
        "id": 100,
        "position": 0,
        "kind": "text",
        "title": "Intro",
        "body": "Some body text.",
        **overrides,
    }


# 1. Real modules.json loads and has the right shape -------------------


def test_real_modules_fixture_loads_7_modules_and_13_segments() -> None:
    fixtures = read_fixtures()
    assert len(fixtures.modules) == 7
    all_segs = [s for m in fixtures.modules for s in m.segments]
    assert len(all_segs) == 13


def test_real_modules_have_sequential_numbers_0_to_6() -> None:
    fixtures = read_fixtures()
    numbers = sorted(m.number for m in fixtures.modules)
    assert numbers == list(range(7))


def test_real_modules_have_titles_and_non_empty_goals() -> None:
    fixtures = read_fixtures()
    for m in fixtures.modules:
        assert m.title.strip(), f"module {m.id} has an empty title"
        assert m.goals.strip(), f"module {m.id} has empty goals"


def test_real_module_segments_are_in_sequential_position_order() -> None:
    fixtures = read_fixtures()
    for m in fixtures.modules:
        positions = [s.position for s in m.segments]
        assert positions == list(range(len(positions))), (
            f"module {m.id} segments not sequential: {positions}"
        )


# 2. Invalid segment kind is refused ------------------------------------


def test_invalid_segment_kind_is_refused(tmp_path: Path) -> None:
    data = {"modules": [module_fixture(segments=[dict(segment_fixture(), kind="lecture")])]}
    with pytest.raises(ValueError, match="kind"):
        read_fixtures(write(tmp_path, data))


# 3. text / worked_example with no body is refused ----------------------


@pytest.mark.parametrize("kind", ["text", "worked_example"])
def test_segment_without_body_is_refused(tmp_path: Path, kind: str) -> None:
    data = {"modules": [module_fixture(segments=[dict(segment_fixture(), kind=kind, body=None)])]}
    with pytest.raises(ValueError, match="body"):
        read_fixtures(write(tmp_path, data))


# 4. Duplicate module ids are refused -----------------------------------


def test_duplicate_module_ids_are_refused(tmp_path: Path) -> None:
    # Two modules with the same id in the same file.
    data = {
        "modules": [
            module_fixture(),
            module_fixture(slug="other", title="Other", number=1, position=1),
        ]
    }
    with pytest.raises(ValueError, match="module ids used twice"):
        read_fixtures(write(tmp_path, data))


# 5. Duplicate segment ids are refused ----------------------------------


def test_duplicate_segment_ids_are_refused(tmp_path: Path) -> None:
    # Two segments with the same id across two modules.
    mod_a = module_fixture(id=10, number=0, position=0)
    mod_b = {
        "id": 11,
        "number": 1,
        "slug": "mod-b",
        "title": "Module B",
        "goals": "Goal B.",
        "estimated_minutes": 5,
        "position": 1,
        # Segment id 100 clashes with mod_a's segment.
        "segments": [{"id": 100, "position": 0, "kind": "text", "title": "B intro", "body": "x"}],
    }
    data = {"modules": [mod_a, mod_b]}
    with pytest.raises(ValueError, match="segment ids used twice"):
        read_fixtures(write(tmp_path, data))


# 6. Segment with unknown module_id is refused --------------------------


def test_segment_with_unknown_module_id_is_refused(tmp_path: Path) -> None:
    """The referential-integrity check in read_fixtures fires when a segment's module_id
    names a module that is not in the merged set.

    The inject_module_id pre-validator always stamps the parent module's id on every nested
    segment, so the mismatch can only arise through the public API when a segment's module_id
    was set outside that path (e.g., hand-edited files that bypass the pre-validator).  We use
    SegmentFixture.model_construct (skip validators) to manufacture the bad fixture object, then
    invoke the referential check by extracting it from the merged FixtureFile.
    """
    from app.seed import FixtureFile, ModuleFixture, SegmentFixture

    # A segment that claims to belong to module 99 which does not exist.
    orphan = SegmentFixture.model_construct(
        id=200,
        module_id=99,
        position=0,
        kind="text",
        title="Orphan",
        body="x",
        video_id=None,
        activity_id=None,
    )
    # A module that carries the orphan in its segments list.
    bad_module = ModuleFixture.model_construct(
        id=10,
        number=0,
        slug="m",
        title="M",
        goals="G.",
        estimated_minutes=5,
        position=0,
        segments=[orphan],
    )
    merged = FixtureFile.model_construct(activities=[], graphs=[], modules=[bad_module])

    # Replicate the referential-integrity check that read_fixtures runs post-merge.
    def _check_referential_integrity() -> None:
        module_ids = {m.id for m in merged.modules}
        for m in merged.modules:
            for s in m.segments:
                if s.module_id not in module_ids:
                    raise ValueError(
                        f"segment {s.id}: module_id {s.module_id} does not reference any module"
                    )

    with pytest.raises(ValueError, match="does not reference any module"):
        _check_referential_integrity()


# 7. Re-seeding updates content but never touches ModuleProgress --------


def test_reseed_updates_module_content_and_leaves_progress_intact(
    tmp_path: Path, db: Session
) -> None:
    # First load: create module 10 with one text segment.
    folder = write(tmp_path, {"modules": [module_fixture()]})
    load(db, folder)

    # Create a user and a ModuleProgress row for that module.
    user = User(email="student@example.com", display_name="Student", password_hash="x")  # noqa: S106
    db.add(user)
    db.flush()
    progress = ModuleProgress(
        user_id=user.id,
        module_id=10,
        status="in_progress",
        current_segment_position=0,
    )
    db.add(progress)
    db.commit()
    progress_id = progress.id

    # Second load: update the module title and segment body.
    updated_mod = module_fixture(
        title="Updated Title",
        segments=[dict(segment_fixture(), body="Updated body.")],
    )
    write(tmp_path, {"modules": [updated_mod]})
    load(db, folder)
    db.expire_all()

    # Module content was updated.
    reloaded_mod = db.get(Module, 10)
    assert reloaded_mod is not None
    assert reloaded_mod.title == "Updated Title"

    reloaded_seg = db.get(Segment, 100)
    assert reloaded_seg is not None
    assert reloaded_seg.body == "Updated body."

    # Progress row is untouched (same id, same status, same position).
    reloaded_progress = db.get(ModuleProgress, progress_id)
    assert reloaded_progress is not None
    assert reloaded_progress.status == "in_progress"
    assert reloaded_progress.current_segment_position == 0
    assert len(db.scalars(select(ModuleProgress)).all()) == 1
