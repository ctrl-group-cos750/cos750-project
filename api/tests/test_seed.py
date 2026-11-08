"""The content fixtures and their loader (app/seed). The first test is the CI gate the SE
document asks for (NFR-M5): an invalid fixture fails the build."""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, GraphScenario, Hint, User
from app.seed import load, read_fixtures


def test_every_committed_fixture_is_valid() -> None:
    read_fixtures()  # raises, naming the file, if any fixture is invalid


def test_modules_2_to_6_have_placeholder_retrieval_items() -> None:
    content = read_fixtures()
    retrieval = [activity for activity in content.activities if activity.purpose == "retrieval"]
    assert {activity.module_id for activity in retrieval} == {2, 3, 4, 5, 6}
    assert all(activity.kind == "multiple_choice" for activity in retrieval)
    assert all(activity.objective_id is None for activity in retrieval)


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
