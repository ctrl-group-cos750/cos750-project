"""Loads content from the JSON fixtures in this folder (SE document §8 "Content is loaded from
fixtures", NFR-M5). Run it with `python -m app.seed`; the API container does on every start.

Each fixture file holds `activities`, each with its `hints`, and `graphs`, the scenarios the BFS
visualiser loads (FR-6.1), all with fixed ids so a re-run updates the same rows. Re-running replaces
content only: students' attempts and hint views are never touched.
Videos and their checkpoints are not fixtures: staff make them in the app's video editor, because
the media is uploaded to a volume, not committed (/staff/videos, app/routers/staff.py).

Every file is validated first, against the same schemas the checker uses, and every graph is run
through the BFS engine, so a broken fixture stops the load (and CI, see tests/test_seed.py) before
anything is written.
"""

import json
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.models import Activity, GraphScenario, Hint
from app.schemas.activities import (
    ActivityKind,
    FillInConfig,
    FillInSolution,
    MultipleChoiceConfig,
    MultipleChoiceSolution,
    ParsonsConfig,
    ParsonsSolution,
    TraceConfig,
)
from app.schemas.base import ApiModel
from app.schemas.graphs import VERTEX, GraphScenarioOut
from app.services.bfs import InvalidGraph, run_bfs

FIXTURES = Path(__file__).parent


class NoSolution(ApiModel):
    """A kind with no stored answer: the server derives it (e.g. trace, checked against the BFS
    engine, FR-6.6). Its fixture solution must be empty, `{}`."""


# The config and solution schemas for each kind (FR-4.1). Add a kind here when its checker lands.
SHAPES: dict[str, tuple[type[BaseModel], type[BaseModel]]] = {
    "multiple_choice": (MultipleChoiceConfig, MultipleChoiceSolution),
    "parsons": (ParsonsConfig, ParsonsSolution),
    "fill_in": (FillInConfig, FillInSolution),
    "trace": (TraceConfig, NoSolution),
}


class HintFixture(BaseModel, extra="forbid"):
    level: int = Field(ge=1, le=4)
    body: str = Field(min_length=1)


class ActivityFixture(BaseModel, extra="forbid"):
    id: int
    kind: ActivityKind
    title: str = Field(max_length=200)
    visible: bool = True
    config: dict[str, Any]
    solution: dict[str, Any]
    hints: list[HintFixture] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def check_shapes(self) -> "ActivityFixture":
        config_shape, solution_shape = SHAPES[self.kind]
        config = config_shape.model_validate(self.config)
        solution = solution_shape.model_validate(self.solution)
        if isinstance(config, MultipleChoiceConfig) and isinstance(
            solution, MultipleChoiceSolution
        ):
            ids = {option.id for option in config.options}
            if solution.correct not in ids:
                raise ValueError(
                    f"activity {self.id}: correct option {solution.correct!r} is not one of the options"
                )
            if unknown := set(solution.feedback) - ids:
                raise ValueError(
                    f"activity {self.id}: feedback for unknown options {sorted(unknown)}"
                )
        if isinstance(config, TraceConfig):
            # The traversal is the engine's, so a graph it refuses would only fail when a student
            # opens it; catch it at load, like GraphFixture does (FR-6.6).
            try:
                run_bfs(GraphScenarioOut(id=0, name="", **config.model_dump()))
            except InvalidGraph as exc:
                raise ValueError(f"activity {self.id}: {exc}") from exc
        levels = [hint.level for hint in self.hints]
        if len(levels) != len(set(levels)):
            raise ValueError(f"activity {self.id}: two hints share a level")
        return self


class GraphEdgeFixture(BaseModel, extra="forbid"):
    source: str
    target: str


class GraphFixture(BaseModel, extra="forbid"):
    id: int
    name: str = Field(min_length=1, max_length=200)
    directed: bool = False
    # Up to about 50 vertices, the size the engine and the visualiser are designed for (§10).
    vertices: list[Annotated[str, Field(pattern=VERTEX)]] = Field(min_length=1, max_length=50)
    edges: list[GraphEdgeFixture] = Field(default_factory=list)
    start_vertex: str

    @model_validator(mode="after")
    def check_runs(self) -> "GraphFixture":
        """A graph the engine refuses (unknown start, repeated vertex, edge to an unknown vertex)
        would only fail when a student opens it, so refuse it here instead."""
        try:
            run_bfs(GraphScenarioOut.model_validate(self.model_dump()))
        except InvalidGraph as exc:
            raise ValueError(f"graph {self.id}: {exc}") from exc
        return self


class FixtureFile(BaseModel, extra="forbid"):
    activities: list[ActivityFixture] = Field(default_factory=list)
    graphs: list[GraphFixture] = Field(default_factory=list)


def read_fixtures(folder: Path = FIXTURES) -> FixtureFile:
    """Every fixture file in `folder`, validated and merged. Raises ValueError naming the file and
    the problem if any file is invalid or if two activities, or two graphs, share an id."""
    merged = FixtureFile()
    for path in sorted(folder.glob("*.json")):
        try:
            data = FixtureFile.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (ValidationError, json.JSONDecodeError) as exc:
            raise ValueError(f"{path.name}: {exc}") from exc
        merged.activities.extend(data.activities)
        merged.graphs.extend(data.graphs)
    for what, ids in (
        ("activity", [a.id for a in merged.activities]),
        ("graph", [g.id for g in merged.graphs]),
    ):
        if dupes := sorted({i for i in ids if ids.count(i) > 1}):
            raise ValueError(f"{what} ids used twice: {dupes}")
    return merged


def load(session: Session, folder: Path = FIXTURES) -> FixtureFile:
    """Validate every fixture, then insert or update its rows in one transaction."""
    content = read_fixtures(folder)
    for a in content.activities:
        session.merge(
            Activity(
                id=a.id,
                kind=a.kind,
                title=a.title,
                visible=a.visible,
                config=a.config,
                solution=a.solution,
            )
        )
        session.flush()
        session.execute(delete(Hint).where(Hint.activity_id == a.id))
        session.add_all(Hint(activity_id=a.id, level=h.level, body=h.body) for h in a.hints)
    for g in content.graphs:
        session.merge(
            GraphScenario(
                id=g.id,
                name=g.name,
                directed=g.directed,
                vertices=g.vertices,
                edges=[edge.model_dump() for edge in g.edges],
                start_vertex=g.start_vertex,
            )
        )
    session.flush()
    if session.get_bind().dialect.name == "postgresql":
        # Fixed ids don't move Postgres's id sequences; move them past the largest id, so a row
        # added without an id later doesn't collide with seeded content.
        for table in ("activities", "graph_scenarios"):
            session.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "  # noqa: S608 (fixed names)
                    f"GREATEST((SELECT MAX(id) FROM {table}), 1))"
                )
            )
    session.commit()
    return content
