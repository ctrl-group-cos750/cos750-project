"""Loads content from the JSON fixtures in this folder (SE document §8 "Content is loaded from
fixtures", NFR-M5). Run it with `python -m app.seed`; the API container does on every start.

Each fixture file may hold any of:
- `objectives`: the learning objectives, numbered as in the ID document (Table 1).
- `modules`: modules 0 to 6 (ID document Table 4), each with its `segments` in the order a student
  meets them (FR-2.2). Positions come from that order.
- `activities`, each with its `hints`, and tagged with its `module_id`, `objective_id` and
  `purpose` (FR-4.3).
- `graphs`: the scenarios the BFS visualiser loads (FR-6.1).
- `review_paths`: one per objective, the path a student opens when the mastery check marks that
  objective "not yet" (FR-7.5, ID document §7.6): `segments` that teach it again (a worked
  example, with practice activities of purpose `review`), then fresh items of purpose `mastery`.
  Its activities belong to no module. Numbered from 1000 + 100 times the objective (objective 5:
  1501, 1502, …), in `review.json`.

The fixtures seed the database; the database is the content from then on. Staff edit it in the
portal (app/routers/staff_content.py), and an edited row is marked (`edited_at`, or
`segments_edited_at` for a module's list of segments). A re-run inserts what is missing and
updates what nobody has edited, but never writes over a staff edit: those are listed in `kept`
and stay as staff left them. To bring the repository back, staff use "Use the repository's
version" on that item. Or they export the portal's content as fixtures and commit them: an edited
row the fixtures now match is no longer marked edited (`caught_up`), so the repository decides
again. After loading, the whole of the content is checked again (`database_problem`), since the
fixtures and the staff edits can each be fine and still not fit together; a problem is reported,
not raised.

Everything has a fixed id, so a re-run updates the same rows. By convention a module's segments and
activities are numbered from 100 times its number (module 3: 301, 302, …; module 0: 1, 2, …), and a
module lives in its own file (`module-3.json`), so content for different modules never collides.
Re-running replaces content only: students' attempts and hint views are never touched, and their
objective results are worked out again from those attempts, so a changed rule applies to everyone. A segment
removed from a module's fixture is removed from the database; a video that played it is kept and
simply has no segment until staff choose another.
Videos and their checkpoints are not fixtures: staff make them in the app's video editor, because
the media is uploaded to a volume, not committed (/staff/videos, app/routers/staff.py).

Every file is validated first, against the same schemas the checker uses, and every graph is run
through the BFS engine, so a broken fixture stops the load (and CI, see tests/test_seed.py) before
anything is written.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, TypeVar

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import delete, insert, literal, select, text, update
from sqlalchemy.orm import Session

from app.models import (
    Activity,
    Attempt,
    Checkpoint,
    GraphScenario,
    Hint,
    HintView,
    Module,
    Objective,
    Segment,
    ShownSegment,
    Video,
)
from app.schemas.activities import ActivityKind
from app.schemas.content import Purpose, SegmentKind
from app.schemas.graphs import VERTEX, GraphScenarioOut
from app.services.bfs import InvalidGraph, run_bfs
from app.services.content import validate_activity
from app.services.mastery import MASTERY_MODULE, recompute_all
from app.services.modules import keep_places, segment_order

FIXTURES = Path(__file__).parent
# One example activity per kind, for authors to copy (README.md in this folder). The loader reads
# only the *.json files directly in FIXTURES, so these are never loaded as content.
TEMPLATES = FIXTURES / "templates"

# Activities come from two places: the fixtures, and the video editor (a checkpoint's question,
# made in the app). They share one table, so they get separate id ranges: fixtures stay below
# EDITOR_IDS_FROM, and the editor's start there. Otherwise a fixture would overwrite an editor
# question that happens to have its id: `load` writes fixtures by id.
EDITOR_IDS_FROM = 100_000
# Activities, segments and graphs made in the content editor (app/routers/staff_content.py) are
# numbered from here, below the video editor's range, so the portal's content can be exported and
# committed as fixtures. Hand-written fixtures keep to ids below this by convention.
PORTAL_IDS_FROM = 50_000


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
        if self.purpose == "retrieval":
            if self.module_id not in range(2, 7):
                raise ValueError(f"activity {self.id}: a retrieval item belongs in module 2 to 6")
            if self.kind != "multiple_choice":
                raise ValueError(f"activity {self.id}: retrieval items must be multiple choice")
        return self


class ObjectiveFixture(BaseModel, extra="forbid"):
    # 1 to 8: each objective has a badge, and the badge catalogue has lo1 to lo8
    # (app/services/rewards.py, web/src/components/achievements.ts). Add one there first.
    id: int = Field(ge=1, le=8)
    text: str = Field(min_length=1)
    bloom_level: str = Field(min_length=1, max_length=100)
    criterion: str = Field(min_length=1)
    # The criterion as the rule the mastery service counts over the parts of the module 6 items
    # (app/services/mastery.py): at least this fraction right ("4 of 5" is 0.8) ...
    pass_fraction: float | None = Field(default=None, gt=0, le=1)
    # ... or at most this many wrong ("with at most one error" is 1). Exactly one of the two.
    max_wrong: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def one_rule(self) -> "ObjectiveFixture":
        if (self.pass_fraction is None) == (self.max_wrong is None):
            raise ValueError(f"objective {self.id}: give pass_fraction or max_wrong, not both")
        return self


class SegmentFixture(BaseModel, extra="forbid"):
    id: int
    kind: SegmentKind
    title: str = Field(min_length=1, max_length=200)
    body: str = ""  # Markdown
    activity_id: int | None = None
    skip_check_activity_id: int | None = None
    refresher_for: str | None = Field(default=None, min_length=1, max_length=100)
    # Support for this objective (FR-8.4, #172): shown only to a student struggling with it in
    # this module (app/services/support.py). Only in modules 0 to 5; see `check_references`.
    support_for: int | None = Field(default=None, ge=1, le=8)

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
        if self.support_for is not None:
            if self.kind not in SUPPORT_KINDS:
                raise ValueError(
                    f"segment {self.id}: support is a text, worked example or activity segment, "
                    f"not a {self.kind}"
                )
            if self.skip_check_activity_id is not None:
                raise ValueError(
                    f"segment {self.id}: a support segment can't be skipped by a check"
                )
        return self


# What a support segment (FR-8.4) can be: a worked example, in text, or a fresh practice item.
SUPPORT_KINDS = ("text", "worked_example", "activity")


class ModuleFixture(BaseModel, extra="forbid"):
    id: int = Field(ge=0, le=20)  # the module's number
    slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=100)
    title: str = Field(min_length=1, max_length=200)
    goals: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)
    estimated_minutes: int = Field(gt=0, le=120)
    segments: list[SegmentFixture] = Field(default_factory=list)


class ReviewPathFixture(BaseModel, extra="forbid"):
    objective_id: int = Field(ge=1, le=8)
    segments: list[SegmentFixture] = Field(min_length=1)

    @model_validator(mode="after")
    def check_segments(self) -> "ReviewPathFixture":
        if any(seg.support_for is not None for seg in self.segments):
            raise ValueError(
                f"review path {self.objective_id}: support segments (support_for) belong in "
                "modules 0 to 5; the review path is already the objective's corrective step"
            )
        if any(seg.kind == "refresher" for seg in self.segments):
            raise ValueError(f"review path {self.objective_id}: a refresher belongs in module 0")
        # ID document §7.6: the path starts by teaching the objective again.
        if self.segments[0].kind == "activity":
            raise ValueError(
                f"review path {self.objective_id}: starts with a segment that teaches the "
                "objective again, such as a worked example"
            )
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
    objectives: list[ObjectiveFixture] = Field(default_factory=list)
    modules: list[ModuleFixture] = Field(default_factory=list)
    activities: list[ActivityFixture] = Field(default_factory=list)
    graphs: list[GraphFixture] = Field(default_factory=list)
    review_paths: list[ReviewPathFixture] = Field(default_factory=list)


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
    retrieval_counts: dict[int, int] = {}
    for activity in content.activities:
        if activity.purpose == "retrieval" and activity.module_id is not None:
            retrieval_counts[activity.module_id] = retrieval_counts.get(activity.module_id, 0) + 1
    if modules_with_too_many := sorted(
        module_id for module_id, count in retrieval_counts.items() if count > 2
    ):
        raise ValueError(f"modules may have at most two retrieval items: {modules_with_too_many}")
    on_paths = _check_review_paths(content, objectives, activities)
    # Module 6 is the mastery check: every objective needs an item there, or its result could
    # never be met and no student could ever be ready for the lecture (FR-7.1, FR-7.4).
    if MASTERY_MODULE in modules:
        checked = {
            a.objective_id
            for a in content.activities
            if a.module_id == MASTERY_MODULE and a.purpose == "mastery"
        }
        if missing := sorted(objectives - checked):
            raise ValueError(
                f"module {MASTERY_MODULE} has no mastery item for objectives {missing}"
            )
    placed: dict[int, int] = {}  # activity id -> the segment that shows it
    for m in content.modules:
        for seg in m.segments:
            if seg.activity_id in on_paths:
                raise ValueError(
                    f"segment {seg.id}: activity {seg.activity_id} is on a review path"
                )
            for ref in (seg.activity_id, seg.skip_check_activity_id):
                if ref is not None and ref not in activities:
                    raise ValueError(f"segment {seg.id}: no activity {ref}")
                # The module page asks its retrieval questions before the segments (FR-2.4), so
                # one placed in a segment as well would be asked twice.
                if ref is not None and activities[ref].purpose == "retrieval":
                    raise ValueError(
                        f"segment {seg.id}: activity {ref} is a retrieval question, which the "
                        "module asks before its segments, not in one"
                    )
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
        _check_support(m, objectives, activities)


def _check_support(
    m: ModuleFixture, objectives: set[int], activities: dict[int, ActivityFixture]
) -> None:
    """A module's support segments (FR-8.4, app/services/support.py). Never in module 6: the
    mastery check is the same for everyone (FR-7.1). Each is for an objective that exists; a support
    activity is a practice item on that objective; and the module has a base practice item on it
    (an activity segment that isn't support) before its first support segment for it, or nothing
    could ever show the support."""
    base_before: set[int] = set()  # objectives with base practice so far, in segment order
    for seg in m.segments:
        activity = activities.get(seg.activity_id) if seg.activity_id is not None else None
        if seg.support_for is None:
            if activity is not None and activity.purpose == "practice" and activity.objective_id:
                base_before.add(activity.objective_id)
            continue
        if m.id == MASTERY_MODULE:
            raise ValueError(
                f"segment {seg.id}: module {MASTERY_MODULE} is the mastery check, the same for "
                "everyone, so it has no support segments"
            )
        if seg.support_for not in objectives:
            raise ValueError(
                f"segment {seg.id}: support for objective {seg.support_for}, which doesn't exist"
            )
        if activity is not None and (
            activity.purpose != "practice" or activity.objective_id != seg.support_for
        ):
            raise ValueError(
                f"segment {seg.id}: a support activity is a practice item on objective "
                f"{seg.support_for}; activity {activity.id} is {activity.purpose} on objective "
                f"{activity.objective_id}"
            )
        if seg.support_for not in base_before:
            raise ValueError(
                f"segment {seg.id}: support for objective {seg.support_for} needs a practice item "
                f"on that objective earlier in module {m.id}, or nothing could ever show it"
            )


def _check_review_paths(
    content: FixtureFile, objectives: set[int], activities: dict[int, ActivityFixture]
) -> set[int]:
    """Each review path: for an objective that exists, one per objective, and every objective has
    one once module 6 does (a student marked "not yet" must have somewhere to go). Its activities
    are that objective's and belong to no module. As the ID document's §7.6 sets out, there is
    practice (`review`) with the full hint ladder, levels 1 to 4, then fresh items (`mastery`):
    at least one of each, the practice first. A mastery item is in module 6 or on a review path,
    nowhere else. Returns the ids of the activities on review paths."""
    paths = [r.objective_id for r in content.review_paths]
    if repeated := sorted({o for o in paths if paths.count(o) > 1}):
        raise ValueError(f"objectives with two review paths: {repeated}")
    if unknown := sorted(set(paths) - objectives):
        raise ValueError(f"review paths for objectives that don't exist: {unknown}")
    has_check = MASTERY_MODULE in {m.id for m in content.modules}
    if has_check and (missing := sorted(objectives - set(paths))):
        raise ValueError(f"objectives with no review path: {missing}")
    on_paths: set[int] = set()
    for path in content.review_paths:
        where = f"review path {path.objective_id}"
        purposes = []
        for seg in path.segments:
            if seg.skip_check_activity_id is not None:
                raise ValueError(f"{where}, segment {seg.id}: nothing on a review path is skipped")
            if seg.activity_id is None:
                continue
            a = activities.get(seg.activity_id)
            if a is None:
                raise ValueError(f"{where}, segment {seg.id}: no activity {seg.activity_id}")
            if a.module_id is not None or a.objective_id != path.objective_id:
                raise ValueError(
                    f"{where}, segment {seg.id}: activity {a.id} must have no module and "
                    f"objective {path.objective_id}"
                )
            if a.purpose not in ("review", "mastery"):
                raise ValueError(
                    f"{where}, segment {seg.id}: activity {a.id} is {a.purpose}; a review path "
                    "holds review (practice) and mastery (fresh) items"
                )
            if a.id in on_paths:
                raise ValueError(f"{where}: activity {a.id} is on a review path twice")
            if a.purpose == "review" and sorted(h.level for h in a.hints) != [1, 2, 3, 4]:
                raise ValueError(
                    f"{where}, segment {seg.id}: practice activity {a.id} needs the full hint "
                    "ladder, levels 1 to 4"
                )
            on_paths.add(a.id)
            purposes.append(a.purpose)
        if "review" not in purposes:
            raise ValueError(f"{where}: needs at least one practice (review) activity")
        if "mastery" not in purposes:
            raise ValueError(f"{where}: needs at least one fresh mastery item")
        if "review" in purposes[purposes.index("mastery") :]:
            raise ValueError(f"{where}: the fresh mastery items come after all the practice")
    for a in content.activities:
        if a.purpose == "mastery" and a.module_id != MASTERY_MODULE and a.id not in on_paths:
            raise ValueError(
                f"activity {a.id}: a mastery item belongs in module {MASTERY_MODULE} or on a "
                "review path"
            )
    return on_paths


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
        merged.review_paths.extend(data.review_paths)
    if too_big := sorted(a.id for a in merged.activities if a.id >= EDITOR_IDS_FROM):
        raise ValueError(
            f"activity ids {too_big} are for the video editor: fixtures use ids below "
            f"{EDITOR_IDS_FROM}"
        )
    check_content(merged)
    return merged


def read_templates(
    folder: Path = TEMPLATES, fixtures: Path = FIXTURES
) -> dict[str, ActivityFixture]:
    """Every template in `folder` (one activity, named after its kind), keyed by kind. Each is
    checked as a fixture activity, then added to the committed fixtures and checked with them, so
    a template copied into a module file is valid there too. Raises ValueError naming the file."""
    content = read_fixtures(fixtures)
    templates: dict[str, ActivityFixture] = {}
    for path in sorted(folder.glob("*.json")):
        try:
            activity = ActivityFixture.model_validate(json.loads(path.read_text(encoding="utf-8")))
            if activity.kind != path.stem:
                raise ValueError(f"the file holds a {activity.kind} activity")
            check_content(
                content.model_copy(update={"activities": [*content.activities, activity]})
            )
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"templates/{path.name}: {exc}") from exc
        templates[activity.kind] = activity
    return templates


def check_content(merged: FixtureFile) -> None:
    """The checks across all content, wherever it comes from: the fixtures (`read_fixtures`) or
    the database after a staff edit (app/services/content_editor.py). Ids are unique, slugs are
    unique, and every reference holds (`check_references`). Raises ValueError naming the item."""
    for what, ids in (
        ("objective", [o.id for o in merged.objectives]),
        ("module", [m.id for m in merged.modules]),
        (
            "segment",
            [s.id for m in merged.modules for s in m.segments]
            + [s.id for r in merged.review_paths for s in r.segments],
        ),
        ("activity", [a.id for a in merged.activities]),
        ("graph", [g.id for g in merged.graphs]),
    ):
        if dupes := sorted({i for i in ids if ids.count(i) > 1}):
            raise ValueError(f"{what} ids used twice: {dupes}")
    slugs = [m.slug for m in merged.modules]
    if repeated := sorted({slug for slug in slugs if slugs.count(slug) > 1}):
        raise ValueError(f"module slugs used twice: {repeated}")
    check_references(merged)


# --- The database read back as fixtures --------------------------------------------------------
# The content editor checks every save on these (app/services/content_editor.py), the seed checks
# the content as a whole after a deploy, and it compares a staff edit with the repository's version.


def objective_as_fixture(o: Objective) -> dict[str, Any]:
    return {
        "id": o.id,
        "text": o.text,
        "bloom_level": o.bloom_level,
        "criterion": o.criterion,
        "pass_fraction": o.pass_fraction,
        "max_wrong": o.max_wrong,
    }


def module_as_fixture(m: Module) -> dict[str, Any]:
    """A module without its segments (`segments_as_fixture` reads those)."""
    return {
        "id": m.id,
        "slug": m.slug,
        "title": m.title,
        "goals": m.goals,
        "estimated_minutes": m.estimated_minutes,
    }


def segment_as_fixture(seg: Segment) -> dict[str, Any]:
    return {
        "id": seg.id,
        "kind": seg.kind,
        "title": seg.title,
        "body": seg.body,
        "activity_id": seg.activity_id,
        "skip_check_activity_id": seg.skip_check_activity_id,
        "refresher_for": seg.refresher_for,
        "support_for": seg.support_for,
    }


def segments_as_fixture(session: Session, home: Any) -> list[dict[str, Any]]:
    """The segments `home` selects (a module's, or a review path's), in their order."""
    rows = session.scalars(select(Segment).where(home).order_by(Segment.position, Segment.id))
    return [segment_as_fixture(seg) for seg in rows]


def activity_as_fixture(session: Session, a: Activity) -> dict[str, Any]:
    hints = session.scalars(select(Hint).where(Hint.activity_id == a.id).order_by(Hint.level))
    return {
        "id": a.id,
        "kind": a.kind,
        "title": a.title,
        "visible": a.visible,
        "module_id": a.module_id,
        "objective_id": a.objective_id,
        "purpose": a.purpose,
        "config": a.config,
        "solution": a.solution,
        "hints": [{"level": h.level, "body": h.body} for h in hints],
    }


def graph_as_fixture(g: GraphScenario) -> dict[str, Any]:
    return {
        "id": g.id,
        "name": g.name,
        "directed": g.directed,
        "vertices": g.vertices,
        "edges": g.edges,
        "start_vertex": g.start_vertex,
    }


def snapshot(session: Session) -> dict[str, Any]:
    """All the content in the database, in the fixtures' shape (not yet validated)."""
    segments = session.scalars(select(Segment).order_by(Segment.position, Segment.id)).all()
    by_module: dict[int, list[dict[str, Any]]] = {}
    by_path: dict[int, list[dict[str, Any]]] = {}
    for seg in segments:
        if seg.module_id is not None:
            by_module.setdefault(seg.module_id, []).append(segment_as_fixture(seg))
        elif seg.review_objective_id is not None:
            by_path.setdefault(seg.review_objective_id, []).append(segment_as_fixture(seg))
    return {
        "objectives": [
            objective_as_fixture(o)
            for o in session.scalars(select(Objective).order_by(Objective.id))
        ],
        "modules": [
            {**module_as_fixture(m), "segments": by_module.get(m.id, [])}
            for m in session.scalars(select(Module).order_by(Module.position, Module.id))
        ],
        "activities": [
            activity_as_fixture(session, a)
            for a in session.scalars(select(Activity).order_by(Activity.id))
        ],
        "graphs": [
            graph_as_fixture(g)
            for g in session.scalars(select(GraphScenario).order_by(GraphScenario.id))
        ],
        "review_paths": [
            {"objective_id": objective_id, "segments": segs}
            for objective_id, segs in sorted(by_path.items())
        ],
    }


def database_problem(session: Session) -> str | None:
    """What is wrong with the content in the database as a whole, or None: the check the content
    editor runs on every save. The seed runs it after a deploy, because the repository's content
    and the portal's edits are each fine on their own but may not fit together, and then every
    save in the editor would be refused until someone fixes it."""
    try:
        check_content(FixtureFile.model_validate(snapshot(session)))
    except ValidationError as exc:
        return "; ".join(str(e["msg"]).removeprefix("Value error, ") for e in exc.errors())
    except ValueError as exc:
        return str(exc)
    return None


def _same(fixture: BaseModel, data: Any, exclude: set[str] | None = None) -> bool:
    """The database's version (`data`, in the fixture's shape) is the fixture's."""
    try:
        stored = type(fixture).model_validate(data)
    except ValidationError:
        return False
    return stored.model_dump(exclude=exclude) == fixture.model_dump(exclude=exclude)


def _same_segments(session: Session, home: Any, segments: list[SegmentFixture]) -> bool:
    stored = segments_as_fixture(session, home)
    return len(stored) == len(segments) and all(
        _same(seg, data) for seg, data in zip(segments, stored, strict=True)
    )


# The tables staff edit row by row, each with an `edited_at`.
Edited = TypeVar("Edited", Objective, Module, Activity, GraphScenario)


def load(
    session: Session,
    folder: Path = FIXTURES,
    kept: list[str] | None = None,
    caught_up: list[str] | None = None,
    problems: list[str] | None = None,
) -> FixtureFile:
    """Validate every fixture, then insert or update its rows in one transaction. A row staff have
    edited in the portal is left as it is, and named in `kept` (when given).

    An edit the repository has caught up with (the portal's content was exported and committed,
    so the fixture now says the same) is no longer marked edited: from then on the repository
    decides again, and a later change there reaches the database. It is named in `caught_up`.

    When `problems` is given, the content in the database is then checked as a whole
    (`database_problem`), and a problem is put in `problems` rather than raised: the content is
    loaded either way, and the API should start so staff can fix it in the portal."""
    content = read_fixtures(folder)
    held: list[str] = [] if kept is None else kept
    handed_back: list[str] = [] if caught_up is None else caught_up

    def edited(
        model: type[Edited],
        fixture: ObjectiveFixture | ModuleFixture | ActivityFixture | GraphFixture,
        as_fixture: Callable[[Edited], dict[str, Any]],
        exclude: set[str] | None = None,
    ) -> bool:
        row = session.get(model, fixture.id)
        if row is None or row.edited_at is None:
            return False
        name = f"{model.__tablename__} {row.id}"
        if _same(fixture, as_fixture(row), exclude):
            row.edited_at = None
            handed_back.append(name)
            return False
        held.append(name)
        return True

    move_editor_activities(session)
    # Parents first: activities point at modules and objectives, segments at activities.
    for o in content.objectives:
        if edited(Objective, o, objective_as_fixture):
            continue
        session.merge(
            Objective(
                id=o.id,
                text=o.text,
                bloom_level=o.bloom_level,
                criterion=o.criterion,
                pass_fraction=o.pass_fraction,
                max_wrong=o.max_wrong,
            )
        )
    for m in content.modules:
        if edited(Module, m, module_as_fixture, exclude={"segments"}):
            continue
        clash = session.scalar(select(Module.id).where(Module.slug == m.slug, Module.id != m.id))
        if clash is not None:
            held.append(f"modules {m.id} (module {clash}, made in the portal, uses its slug)")
            continue
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
        if edited(Activity, a, lambda row: activity_as_fixture(session, row)):
            continue
        if a.module_id is not None and session.get(Module, a.module_id) is None:
            held.append(f"activities {a.id} (its module {a.module_id} was held back)")
            continue
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
        module = session.get(Module, m.id)
        if module is None:  # held back above: a portal module uses its slug
            continue
        if module.segments_edited_at is not None:
            if not _same_segments(session, Segment.module_id == m.id, m.segments):
                held.append(f"segments of module {m.id}")
                continue
            module.segments_edited_at = None
            handed_back.append(f"segments of module {m.id}")
        _load_segments(session, m.segments, module_id=m.id)
    for r in content.review_paths:
        objective = session.get_one(Objective, r.objective_id)
        if objective.segments_edited_at is not None:
            home = Segment.review_objective_id == r.objective_id
            if not _same_segments(session, home, r.segments):
                held.append(f"segments of review path {r.objective_id}")
                continue
            objective.segments_edited_at = None
            handed_back.append(f"segments of review path {r.objective_id}")
        _load_segments(session, r.segments, review_objective_id=r.objective_id)
    for g in content.graphs:
        if edited(GraphScenario, g, graph_as_fixture):
            continue
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
    retire_dropped_activities(session, {a.id for a in content.activities})
    # A changed rule or mastery item applies to every student's result straight away (FR-7.6).
    recompute_all(session)
    move_sequences(session)
    session.commit()
    if problems is not None and (problem := database_problem(session)):
        problems.append(problem)
    return content


def move_sequences(session: Session) -> None:
    """On Postgres, move the id sequences past the largest id. Fixed ids don't move them, and a
    row added without an id later would collide with seeded content. The video editor's
    activities start at EDITOR_IDS_FROM, clear of every fixture id."""
    if session.get_bind().dialect.name != "postgresql":
        return
    for table, floor in (
        ("activities", EDITOR_IDS_FROM),
        ("graph_scenarios", 1),
        ("segments", 1),
    ):
        session.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "  # noqa: S608 (fixed names)
                f"GREATEST((SELECT MAX(id) FROM {table}), {floor}))"
            )
        )


def retire_dropped_activities(session: Session, listed: set[int]) -> list[int]:
    """Take out every fixture activity the fixtures no longer list, and return their ids.

    One nobody has used is deleted with its hints. One a student has answered or asked a hint
    for keeps its row, so their history stays, but is hidden and stops being a mastery item: an
    objective whose old placeholder still counted could never be reached. The video editor's
    questions (ids from EDITOR_IDS_FROM) are never touched, and neither is one staff edited in the
    portal or one a staff-edited module still shows: those belong to the portal now.
    """
    dropped = session.scalars(
        select(Activity).where(
            Activity.id < EDITOR_IDS_FROM,
            Activity.id.not_in(listed),
            Activity.edited_at.is_(None),
        )
    ).all()
    retired = []
    for activity in dropped:
        shown = session.scalar(
            select(Segment.id)
            .where(
                (Segment.activity_id == activity.id)
                | (Segment.skip_check_activity_id == activity.id)
            )
            .limit(1)
        )
        if shown is not None:
            continue
        used = any(
            session.scalar(select(child.id).where(child.activity_id == activity.id).limit(1))
            for child in (Attempt, HintView, Checkpoint)
        )
        if used:
            activity.visible = False
            activity.purpose = "practice"
            activity.module_id = None
            activity.objective_id = None
        else:
            session.execute(delete(Hint).where(Hint.activity_id == activity.id))
            session.delete(activity)
        retired.append(activity.id)
    session.flush()
    return retired


def move_editor_activities(session: Session) -> list[int]:
    """Move every video-checkpoint question with an id below EDITOR_IDS_FROM up by that much,
    with everything that points at it, and return the ids it moved.

    The editor's questions were numbered 1, 2, 3, … before the fixtures had activities, so their
    ids can be the same as a fixture's. Moving them first means `load` never writes a fixture over
    one. It runs on every load and finds nothing to do once they have moved.
    """
    low = sorted(
        set(
            session.scalars(
                select(Checkpoint.activity_id).where(Checkpoint.activity_id < EDITOR_IDS_FROM)
            )
        )
    )
    if not low:
        return []
    taken = session.scalars(
        select(Activity.id).where(Activity.id.in_([i + EDITOR_IDS_FROM for i in low]))
    ).all()
    if taken:
        raise ValueError(f"can't move editor activities: ids {sorted(taken)} are already used")
    columns = [c for c in Activity.__table__.columns if c.name != "id"]
    for old in low:
        new = old + EDITOR_IDS_FROM
        session.execute(
            insert(Activity).from_select(
                ["id", *(c.name for c in columns)],
                select(literal(new), *columns).where(Activity.id == old),
            )
        )
        # A checkpoint question belongs to no module or objective, as the editor makes it. A row
        # a fixture already wrote over (staging, 8 Nov) carries the fixture's tags: drop them, so
        # its answers aren't counted as that module's in the pilot data (FR-10).
        session.execute(
            update(Activity)
            .where(Activity.id == new)
            .values(module_id=None, objective_id=None, purpose="practice")
        )
        for child in (Checkpoint, Hint, HintView, Attempt):
            session.execute(update(child).where(child.activity_id == old).values(activity_id=new))
        # A fixture already written over this id (staging, 8 Nov) is still a module's segment:
        # leave that row for `load` to rewrite as the fixture.
        in_a_module = session.scalar(
            select(Segment.id).where(
                (Segment.activity_id == old) | (Segment.skip_check_activity_id == old)
            )
        )
        if in_a_module is None:
            session.execute(delete(Activity).where(Activity.id == old))
    session.flush()
    return low


def _load_segments(
    session: Session,
    segments: list[SegmentFixture],
    *,
    module_id: int | None = None,
    review_objective_id: int | None = None,
) -> None:
    """Make a module's (or an objective's review path's) segments exactly the fixture's, in its
    order. A segment the fixture no longer lists is deleted, after unlinking any video that
    played it."""
    keep = [seg.id for seg in segments]
    before = [] if module_id is None else segment_order(session, module_id)
    home = (
        Segment.module_id == module_id
        if module_id is not None
        else Segment.review_objective_id == review_objective_id
    )
    gone = session.scalars(select(Segment.id).where(home, Segment.id.not_in(keep))).all()
    if gone:
        session.execute(update(Video).where(Video.segment_id.in_(gone)).values(segment_id=None))
        session.execute(delete(ShownSegment).where(ShownSegment.segment_id.in_(gone)))
        session.execute(delete(Segment).where(Segment.id.in_(gone)))
    for position, seg in enumerate(segments, start=1):
        session.merge(
            Segment(
                id=seg.id,
                module_id=module_id,
                review_objective_id=review_objective_id,
                position=position,
                kind=seg.kind,
                title=seg.title,
                body=seg.body,
                activity_id=seg.activity_id,
                skip_check_activity_id=seg.skip_check_activity_id,
                refresher_for=seg.refresher_for,
                support_for=seg.support_for,
            )
        )
    if module_id is not None:
        # New segments (support, #172) put in before a student's place must not move them.
        session.flush()
        keep_places(session, module_id, before)
