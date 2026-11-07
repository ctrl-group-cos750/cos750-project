"""Loads content from the JSON fixtures in this folder (SE document §8 "Content is loaded from
fixtures", NFR-M5). Run it with `python -m app.seed`; the API container does on every start.

Each fixture file may hold any of:
- `objectives`: the learning objectives, numbered as in the ID document (Table 1).
- `modules`: modules 0 to 6 (ID document Table 4), each with its `segments` in the order a student
  meets them (FR-2.2). Positions come from that order.
- `activities`, each with its `hints`, and tagged with its `module_id`, `objective_id` and
  `purpose` (FR-4.3).
- `graphs`: the scenarios the BFS visualiser loads (FR-6.1).

Everything has a fixed id, so a re-run updates the same rows. By convention a module's segments and
activities are numbered from 100 times its number (module 3: 301, 302, …; module 0: 1, 2, …), and a
module lives in its own file (`module-3.json`), so content for different modules never collides.
Re-running replaces content only: students' attempts and hint views are never touched. A segment
removed from a module's fixture is removed from the database; a video that played it is kept and
simply has no segment until staff choose another.
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
from sqlalchemy import delete, select, text, update
from sqlalchemy.orm import Session

from app.models import Activity, GraphScenario, Hint, Module, Objective, Segment, Video
from app.schemas.activities import ActivityKind
from app.schemas.content import Purpose, SegmentKind
from app.schemas.graphs import VERTEX, GraphScenarioOut
from app.services.bfs import InvalidGraph, run_bfs
from app.services.content import validate_activity

FIXTURES = Path(__file__).parent


class HintFixture(BaseModel, extra="forbid"):
    level: int = Field(ge=1, le=4)
    body: str = Field(min_length=1)


class ActivityFixture(BaseModel, extra="forbid"):
    id: int
    kind: ActivityKind
    title: str = Field(max_length=200)
    visible: bool = True
    module_id: int | None = None
    objective_id: int | None = None
    purpose: Purpose = "practice"
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
        # The mastery report is built from mastery and review items, so each needs its objective
        # (FR-7); a diagnostic item tests prior knowledge, which is no objective (FR-8.1).
        if self.purpose in ("mastery", "review") and self.objective_id is None:
            raise ValueError(f"activity {self.id}: a {self.purpose} item needs an objective_id")
        if self.purpose == "diagnostic" and self.objective_id is not None:
            raise ValueError(f"activity {self.id}: a diagnostic item has no objective")
        return self


class ObjectiveFixture(BaseModel, extra="forbid"):
    id: int = Field(ge=1, le=20)
    text: str = Field(min_length=1)
    bloom_level: str = Field(min_length=1, max_length=100)
    criterion: str = Field(min_length=1)


class SegmentFixture(BaseModel, extra="forbid"):
    id: int
    kind: SegmentKind
    title: str = Field(min_length=1, max_length=200)
    body: str = ""  # Markdown
    activity_id: int | None = None
    skip_check_activity_id: int | None = None
    refresher_for: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def check_kind(self) -> "SegmentFixture":
        if (self.kind == "activity") != (self.activity_id is not None):
            raise ValueError(
                f"segment {self.id}: an activity segment needs an activity_id, and only it has one"
            )
        if self.kind in ("text", "worked_example", "refresher") and not self.body.strip():
            raise ValueError(f"segment {self.id}: a {self.kind} segment needs a body")
        if (self.kind == "refresher") != (self.refresher_for is not None):
            raise ValueError(
                f"segment {self.id}: a refresher needs refresher_for (the diagnostic topic), "
                "and only a refresher has one"
            )
        return self


class ModuleFixture(BaseModel, extra="forbid"):
    id: int = Field(ge=0, le=20)  # the module's number
    slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=100)
    title: str = Field(min_length=1, max_length=200)
    goals: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    estimated_minutes: int = Field(gt=0, le=120)
    segments: list[SegmentFixture] = Field(default_factory=list)


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
    objectives: list[ObjectiveFixture] = Field(default_factory=list)
    modules: list[ModuleFixture] = Field(default_factory=list)
    activities: list[ActivityFixture] = Field(default_factory=list)
    graphs: list[GraphFixture] = Field(default_factory=list)


def check_references(content: FixtureFile) -> None:
    """The checks that span files: every id an item points at exists, and nothing contradicts
    where an activity says it belongs. Raises ValueError naming the item."""
    objectives = {o.id for o in content.objectives}
    modules = {m.id for m in content.modules}
    activities = {a.id: a for a in content.activities}
    for a in content.activities:
        if a.module_id is not None and a.module_id not in modules:
            raise ValueError(f"activity {a.id}: no module {a.module_id}")
        if a.objective_id is not None and a.objective_id not in objectives:
            raise ValueError(f"activity {a.id}: no objective {a.objective_id}")
    placed: dict[int, int] = {}  # activity id -> the segment that shows it
    for m in content.modules:
        for seg in m.segments:
            for ref in (seg.activity_id, seg.skip_check_activity_id):
                if ref is not None and ref not in activities:
                    raise ValueError(f"segment {seg.id}: no activity {ref}")
            if seg.activity_id is None:
                continue
            if seg.activity_id in placed:
                raise ValueError(
                    f"segment {seg.id}: activity {seg.activity_id} is already shown by segment "
                    f"{placed[seg.activity_id]}"
                )
            placed[seg.activity_id] = seg.id
            home = activities[seg.activity_id].module_id
            if home is not None and home != m.id:
                raise ValueError(
                    f"segment {seg.id}: activity {seg.activity_id} belongs to module {home}, "
                    f"not module {m.id}"
                )


def read_fixtures(folder: Path = FIXTURES) -> FixtureFile:
    """Every fixture file in `folder`, validated and merged. Raises ValueError naming the file and
    the problem if any file is invalid or if two activities, or two graphs, share an id."""
    merged = FixtureFile()
    for path in sorted(folder.glob("*.json")):
        try:
            data = FixtureFile.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (ValidationError, json.JSONDecodeError) as exc:
            raise ValueError(f"{path.name}: {exc}") from exc
        merged.objectives.extend(data.objectives)
        merged.modules.extend(data.modules)
        merged.activities.extend(data.activities)
        merged.graphs.extend(data.graphs)
    for what, ids in (
        ("objective", [o.id for o in merged.objectives]),
        ("module", [m.id for m in merged.modules]),
        ("segment", [s.id for m in merged.modules for s in m.segments]),
        ("activity", [a.id for a in merged.activities]),
        ("graph", [g.id for g in merged.graphs]),
    ):
        if dupes := sorted({i for i in ids if ids.count(i) > 1}):
            raise ValueError(f"{what} ids used twice: {dupes}")
    slugs = [m.slug for m in merged.modules]
    if repeated := sorted({slug for slug in slugs if slugs.count(slug) > 1}):
        raise ValueError(f"module slugs used twice: {repeated}")
    check_references(merged)
    return merged


def load(session: Session, folder: Path = FIXTURES) -> FixtureFile:
    """Validate every fixture, then insert or update its rows in one transaction."""
    content = read_fixtures(folder)
    # Parents first: activities point at modules and objectives, segments at activities.
    for o in content.objectives:
        session.merge(
            Objective(id=o.id, text=o.text, bloom_level=o.bloom_level, criterion=o.criterion)
        )
    for m in content.modules:
        session.merge(
            Module(
                id=m.id,
                slug=m.slug,
                title=m.title,
                goals=m.goals,
                estimated_minutes=m.estimated_minutes,
                position=m.id,
            )
        )
    session.flush()
    for a in content.activities:
        session.merge(
            Activity(
                id=a.id,
                kind=a.kind,
                title=a.title,
                visible=a.visible,
                module_id=a.module_id,
                objective_id=a.objective_id,
                purpose=a.purpose,
                config=a.config,
                solution=a.solution,
            )
        )
        session.flush()
        session.execute(delete(Hint).where(Hint.activity_id == a.id))
        session.add_all(Hint(activity_id=a.id, level=h.level, body=h.body) for h in a.hints)
    session.flush()
    for m in content.modules:
        _load_segments(session, m)
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
        for table in ("activities", "graph_scenarios", "segments"):
            session.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "  # noqa: S608 (fixed names)
                    f"GREATEST((SELECT MAX(id) FROM {table}), 1))"
                )
            )
    session.commit()
    return content


def _load_segments(session: Session, module: ModuleFixture) -> None:
    """Make the module's segments exactly the fixture's, in its order. A segment the fixture no
    longer lists is deleted, after unlinking any video that played it."""
    keep = [seg.id for seg in module.segments]
    gone = session.scalars(
        select(Segment.id).where(Segment.module_id == module.id, Segment.id.not_in(keep))
    ).all()
    if gone:
        session.execute(update(Video).where(Video.segment_id.in_(gone)).values(segment_id=None))
        session.execute(delete(Segment).where(Segment.id.in_(gone)))
    for position, seg in enumerate(module.segments, start=1):
        session.merge(
            Segment(
                id=seg.id,
                module_id=module.id,
                position=position,
                kind=seg.kind,
                title=seg.title,
                body=seg.body,
                activity_id=seg.activity_id,
                skip_check_activity_id=seg.skip_check_activity_id,
                refresher_for=seg.refresher_for,
            )
        )
