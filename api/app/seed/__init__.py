"""Loads content from the JSON fixtures in this folder (SE document §8 "Content is loaded from
fixtures", NFR-M5). Run it with `python -m app.seed`; the API container does on every start.

Each fixture file holds `activities`, each with its `hints`, `graphs`, the scenarios the BFS
visualiser loads (FR-6.1), and `modules`, each with its `segments` — all with fixed ids so a
re-run updates the same rows. Re-running replaces content only: students' attempts, hint views
and progress rows are never touched.
Videos and their checkpoints are not fixtures: staff make them in the app's video editor, because
the media is uploaded to a volume, not committed (/staff/videos, app/routers/staff.py).

Every file is validated first, against the same schemas the checker uses, and every graph is run
through the BFS engine, so a broken fixture stops the load (and CI, see tests/test_seed.py) before
anything is written.
"""

import json
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.models import Activity, GraphScenario, Hint, Module, Segment
from app.schemas.activities import ActivityKind
from app.schemas.graphs import VERTEX, GraphScenarioOut
from app.services.bfs import InvalidGraph, run_bfs
from app.services.content import validate_activity

FIXTURES = Path(__file__).parent

# The config and solution schemas for each kind (FR-4.1). Add a kind here when its checker lands.


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
        """The kind's shapes, and a solution a student can reach (app/services/content.py)."""
        try:
            validate_activity(self.kind, self.config, self.solution)
        except ValueError as exc:
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


# The set of valid segment kinds (mirrors the Segment model's kind column).
SegmentKind = Literal["video", "text", "worked_example", "activity", "refresher"]


class SegmentFixture(BaseModel, extra="forbid"):
    id: int
    # module_id is set either directly in the JSON or injected by ModuleFixture.check_segments.
    module_id: int
    position: int = Field(ge=0)
    kind: SegmentKind
    title: str = Field(min_length=1, max_length=200)
    # Required and non-empty for text / worked_example segments.
    body: str | None = None
    # Required for video segments.
    video_id: int | None = None
    # Required for activity segments.
    activity_id: int | None = None

    @model_validator(mode="after")
    def check_kind_fields(self) -> "SegmentFixture":
        if self.kind in ("text", "worked_example") and not self.body:
            raise ValueError(f"segment {self.id}: kind '{self.kind}' requires a non-empty body")
        if self.kind == "video" and self.video_id is None:
            raise ValueError(f"segment {self.id}: kind 'video' requires a video_id")
        if self.kind == "activity" and self.activity_id is None:
            raise ValueError(f"segment {self.id}: kind 'activity' requires an activity_id")
        return self


class ModuleFixture(BaseModel, extra="forbid"):
    id: int
    number: int = Field(ge=0, le=6)
    slug: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    goals: str = Field(min_length=1)
    estimated_minutes: int = Field(ge=1)
    position: int = Field(ge=0)
    # Segments are nested under each module in the JSON for readability; they are flattened and
    # their module_id is injected before validation of each SegmentFixture.
    segments: list[SegmentFixture] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def inject_module_id(cls, data: Any) -> Any:
        """Copy the module id into every nested segment so SegmentFixture.module_id is set."""
        if isinstance(data, dict) and "segments" in data:
            module_id = data.get("id")
            data = dict(data)
            data["segments"] = [
                dict(seg, module_id=module_id) if isinstance(seg, dict) else seg
                for seg in data["segments"]
            ]
        return data

    @model_validator(mode="after")
    def check_segments(self) -> "ModuleFixture":
        """Segment positions within a module must be 0-based and sequential (no gaps)."""
        positions = [s.position for s in self.segments]
        if positions != list(range(len(positions))):
            raise ValueError(
                f"module {self.id}: segment positions must be sequential starting at 0, "
                f"got {positions}"
            )
        return self


class FixtureFile(BaseModel, extra="forbid"):
    activities: list[ActivityFixture] = Field(default_factory=list)
    graphs: list[GraphFixture] = Field(default_factory=list)
    modules: list[ModuleFixture] = Field(default_factory=list)


def read_fixtures(folder: Path = FIXTURES) -> FixtureFile:
    """Every fixture file in `folder`, validated and merged. Raises ValueError naming the file and
    the problem if any file is invalid or if two activities, two graphs, two modules, or two
    segments share an id."""
    merged = FixtureFile()
    for path in sorted(folder.glob("*.json")):
        try:
            data = FixtureFile.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (ValidationError, json.JSONDecodeError) as exc:
            raise ValueError(f"{path.name}: {exc}") from exc
        merged.activities.extend(data.activities)
        merged.graphs.extend(data.graphs)
        merged.modules.extend(data.modules)
    # Validate referential integrity: every segment's module_id must name a real module.
    module_ids = {m.id for m in merged.modules}
    for m in merged.modules:
        for s in m.segments:
            if s.module_id not in module_ids:
                raise ValueError(
                    f"segment {s.id}: module_id {s.module_id} does not reference any module"
                )
    # Collect all segments (flattened) for the duplicate-id check.
    all_segments = [s for m in merged.modules for s in m.segments]
    for what, ids in (
        ("activity", [a.id for a in merged.activities]),
        ("graph", [g.id for g in merged.graphs]),
        ("module", [m.id for m in merged.modules]),
        ("segment", [s.id for s in all_segments]),
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
    for m in content.modules:
        session.merge(
            Module(
                id=m.id,
                number=m.number,
                slug=m.slug,
                title=m.title,
                goals=m.goals,
                estimated_minutes=m.estimated_minutes,
                position=m.position,
            )
        )
        session.flush()
        for s in m.segments:
            session.merge(
                Segment(
                    id=s.id,
                    module_id=s.module_id,
                    position=s.position,
                    kind=s.kind,
                    title=s.title,
                    body=s.body,
                    video_id=s.video_id,
                    activity_id=s.activity_id,
                )
            )
    session.flush()
    if session.get_bind().dialect.name == "postgresql":
        # Fixed ids don't move Postgres's id sequences; move them past the largest id, so a row
        # added without an id later doesn't collide with seeded content.
        for table in ("activities", "graph_scenarios", "modules", "segments"):
            session.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "  # noqa: S608 (fixed names)
                    f"GREATEST((SELECT MAX(id) FROM {table}), 1))"
                )
            )
    session.commit()
    return content
