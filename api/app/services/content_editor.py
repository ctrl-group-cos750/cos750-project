"""The staff content editor (app/routers/staff_content.py): content lives in the database, the
fixtures seed it, and staff edit it here.

Every save follows the same steps: check the item on its own with the fixture models, apply it,
mark it edited (so the seed leaves it alone), then check all the content together with the same
cross-checks CI runs on the fixtures (`check_content`). If either check fails, nothing is kept and
the problem comes back as `ContentProblem`. Students' results are worked out again afterwards, so
a changed mastery item or rule applies to everyone at once (FR-7.6).

Staff-made activities, segments and graphs get ids from PORTAL_IDS_FROM, which is below the video
editor's range, so `export_fixtures` can turn the database back into fixture files to commit.
"""

import io
import json
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models import (
    Activity,
    Attempt,
    Checkpoint,
    GraphScenario,
    Hint,
    HintView,
    Module,
    ModuleProgress,
    Objective,
    Segment,
    Video,
)
from app.schemas.staff_content import (
    EditorActivityIn,
    EditorActivityOut,
    EditorActivitySummary,
    EditorContentOverview,
    EditorGraphIn,
    EditorGraphOut,
    EditorGraphSummary,
    EditorModuleIn,
    EditorModuleOut,
    EditorModuleSummary,
    EditorObjectiveIn,
    EditorObjectiveOut,
    EditorReviewPathOut,
    EditorReviewPathSummary,
    EditorSegmentIn,
    EditorSegmentOut,
    EditorVideoChoice,
)
from app.seed import (
    EDITOR_IDS_FROM,
    FIXTURES,
    PORTAL_IDS_FROM,
    ActivityFixture,
    FixtureFile,
    GraphFixture,
    ModuleFixture,
    ObjectiveFixture,
    ReviewPathFixture,
    SegmentFixture,
    check_content,
    load,
    read_fixtures,
)
from app.services.mastery import recompute_all


class ContentProblem(ValueError):
    """The edit breaks a content rule; the message says which, for the editor to show."""


class NotFound(LookupError):
    pass


class Conflict(ValueError):
    """The edit can't be made as asked (it belongs to another editor, or the repository would
    bring it back); the message says what to do instead."""


def _now() -> datetime:
    return datetime.now(UTC)


def _message(exc: ValidationError) -> str:
    """A validation error as one line per problem, without pydantic's URLs."""
    lines = []
    for err in exc.errors():
        where = ".".join(str(part) for part in err["loc"])
        text = str(err["msg"]).removeprefix("Value error, ")
        lines.append(f"{where}: {text}" if where else text)
    return "\n".join(lines)


F = TypeVar("F", bound=BaseModel)


def _fixture(model: type[F], data: dict[str, Any]) -> F:  # noqa: UP047 (Python 3.11 here)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ContentProblem(_message(exc)) from exc


@cache
def _repository(folder: Path = FIXTURES) -> FixtureFile:
    """The fixtures as committed. They only change with a new image, so read them once."""
    return read_fixtures(folder)


def _repo_ids() -> dict[str, set[int]]:
    repo = _repository()
    return {
        "objectives": {o.id for o in repo.objectives},
        "modules": {m.id for m in repo.modules},
        "review_paths": {r.objective_id for r in repo.review_paths},
        "activities": {a.id for a in repo.activities},
        "graphs": {g.id for g in repo.graphs},
    }


# --- Reading the database as fixtures ---------------------------------------------------------


def _segment_fixture(seg: Segment) -> dict[str, Any]:
    return {
        "id": seg.id,
        "kind": seg.kind,
        "title": seg.title,
        "body": seg.body,
        "activity_id": seg.activity_id,
        "skip_check_activity_id": seg.skip_check_activity_id,
        "refresher_for": seg.refresher_for,
    }


def _activity_fixture(session: Session, a: Activity) -> dict[str, Any]:
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


def _checkpoint_ids(session: Session) -> set[int]:
    return set(session.scalars(select(Checkpoint.activity_id)))


def _snapshot(session: Session) -> dict[str, Any]:
    """All the content in the database, in the fixtures' shape (not yet validated)."""
    segments = session.scalars(select(Segment).order_by(Segment.position, Segment.id)).all()
    by_module: dict[int, list[dict[str, Any]]] = {}
    by_path: dict[int, list[dict[str, Any]]] = {}
    for seg in segments:
        if seg.module_id is not None:
            by_module.setdefault(seg.module_id, []).append(_segment_fixture(seg))
        elif seg.review_objective_id is not None:
            by_path.setdefault(seg.review_objective_id, []).append(_segment_fixture(seg))
    return {
        "objectives": [
            {
                "id": o.id,
                "text": o.text,
                "bloom_level": o.bloom_level,
                "criterion": o.criterion,
                "pass_fraction": o.pass_fraction,
                "max_wrong": o.max_wrong,
            }
            for o in session.scalars(select(Objective).order_by(Objective.id))
        ],
        "modules": [
            {
                "id": m.id,
                "slug": m.slug,
                "title": m.title,
                "goals": m.goals,
                "estimated_minutes": m.estimated_minutes,
                "segments": by_module.get(m.id, []),
            }
            for m in session.scalars(select(Module).order_by(Module.position, Module.id))
        ],
        "activities": [
            _activity_fixture(session, a)
            for a in session.scalars(select(Activity).order_by(Activity.id))
        ],
        "graphs": [
            {
                "id": g.id,
                "name": g.name,
                "directed": g.directed,
                "vertices": g.vertices,
                "edges": g.edges,
                "start_vertex": g.start_vertex,
            }
            for g in session.scalars(select(GraphScenario).order_by(GraphScenario.id))
        ],
        "review_paths": [
            {"objective_id": objective_id, "segments": segs}
            for objective_id, segs in sorted(by_path.items())
        ],
    }


def check_database(session: Session) -> FixtureFile:
    """All the content in the database, checked as CI checks the fixtures. Raises
    ContentProblem naming the item at fault."""
    content = _fixture(FixtureFile, _snapshot(session))
    try:
        check_content(content)
    except ValueError as exc:
        raise ContentProblem(str(exc)) from exc
    return content


def _commit(session: Session) -> None:
    """Check everything, then keep the edit, or undo it and raise ContentProblem."""
    session.flush()
    try:
        check_database(session)
    except ContentProblem:
        session.rollback()
        raise
    recompute_all(session)
    session.commit()


def _next_id(session: Session, column: Any) -> int:
    """The next free id in the portal's range (PORTAL_IDS_FROM up to the video editor's)."""
    top = session.scalar(
        select(func.max(column)).where(column >= PORTAL_IDS_FROM, column < EDITOR_IDS_FROM)
    )
    return PORTAL_IDS_FROM if top is None else top + 1


# --- Overview ----------------------------------------------------------------------------------


def overview(session: Session) -> EditorContentOverview:
    repo = _repo_ids()
    counts = dict(
        session.execute(
            select(Segment.module_id, func.count())
            .where(Segment.module_id.is_not(None))
            .group_by(Segment.module_id)
        ).all()
    )
    path_counts = dict(
        session.execute(
            select(Segment.review_objective_id, func.count())
            .where(Segment.review_objective_id.is_not(None))
            .group_by(Segment.review_objective_id)
        ).all()
    )
    objectives = session.scalars(select(Objective).order_by(Objective.id)).all()
    checkpoints = _checkpoint_ids(session)
    return EditorContentOverview(
        objectives=[_objective_out(o, repo) for o in objectives],
        modules=[
            EditorModuleSummary(
                id=m.id,
                slug=m.slug,
                title=m.title,
                segment_count=counts.get(m.id, 0),
                edited=m.edited_at is not None,
                segments_edited=m.segments_edited_at is not None,
                in_repository=m.id in repo["modules"],
            )
            for m in session.scalars(select(Module).order_by(Module.position, Module.id))
        ],
        review_paths=[
            EditorReviewPathSummary(
                objective_id=o.id,
                segment_count=path_counts.get(o.id, 0),
                edited=o.segments_edited_at is not None,
                in_repository=o.id in repo["review_paths"],
            )
            for o in objectives
        ],
        activities=[
            EditorActivitySummary(
                id=a.id,
                kind=a.kind,  # type: ignore[arg-type]  # checked when it was stored
                title=a.title,
                module_id=a.module_id,
                objective_id=a.objective_id,
                purpose=a.purpose,  # type: ignore[arg-type]
                edited=a.edited_at is not None,
                in_repository=a.id in repo["activities"],
            )
            for a in session.scalars(select(Activity).order_by(Activity.id))
            if a.id not in checkpoints
        ],
        graphs=[
            EditorGraphSummary(
                id=g.id,
                name=g.name,
                edited=g.edited_at is not None,
                in_repository=g.id in repo["graphs"],
            )
            for g in session.scalars(select(GraphScenario).order_by(GraphScenario.id))
        ],
        videos=[
            EditorVideoChoice(id=v.id, title=v.title, segment_id=v.segment_id)
            for v in session.scalars(select(Video).order_by(Video.title, Video.id))
        ],
    )


# --- Objectives --------------------------------------------------------------------------------


def _objective_out(o: Objective, repo: dict[str, set[int]] | None = None) -> EditorObjectiveOut:
    repo = repo or _repo_ids()
    return EditorObjectiveOut(
        id=o.id,
        text=o.text,
        bloom_level=o.bloom_level,
        criterion=o.criterion,
        pass_fraction=o.pass_fraction,
        max_wrong=o.max_wrong,
        edited=o.edited_at is not None,
        in_repository=o.id in repo["objectives"],
    )


def save_objective(
    session: Session, objective_id: int | None, data: EditorObjectiveIn
) -> EditorObjectiveOut:
    """Create an objective (`objective_id` None: the next number) or change one."""
    if objective_id is None:
        top = session.scalar(select(func.max(Objective.id)))
        new_id = 1 if top is None else top + 1
        row = Objective(id=new_id)
        session.add(row)
    else:
        found = session.get(Objective, objective_id)
        if found is None:
            raise NotFound(f"There is no objective {objective_id}.")
        row = found
    checked = _fixture(ObjectiveFixture, {"id": row.id, **data.model_dump()})
    row.text = checked.text
    row.bloom_level = checked.bloom_level
    row.criterion = checked.criterion
    row.pass_fraction = checked.pass_fraction
    row.max_wrong = checked.max_wrong
    row.edited_at = _now()
    _commit(session)
    return _objective_out(row)


# --- Segments (a module's or a review path's) --------------------------------------------------


def _segments_out(session: Session, segments: list[Segment]) -> list[EditorSegmentOut]:
    videos = {
        v.segment_id: v.id
        for v in session.scalars(
            select(Video).where(Video.segment_id.in_([s.id for s in segments]))
        )
    }
    return [
        EditorSegmentOut(
            id=s.id,
            kind=s.kind,  # type: ignore[arg-type]  # checked when it was stored
            title=s.title,
            body=s.body,
            activity_id=s.activity_id,
            skip_check_activity_id=s.skip_check_activity_id,
            refresher_for=s.refresher_for,
            video_id=videos.get(s.id),
        )
        for s in segments
    ]


def _segment_rows(session: Session, home: Any) -> list[Segment]:
    return list(session.scalars(select(Segment).where(home).order_by(Segment.position, Segment.id)))


def _same_segments(rows: list[Segment], incoming: list[EditorSegmentIn]) -> bool:
    """The incoming list says exactly what is stored already (so saving changes nothing)."""
    return [_segment_fixture(r) for r in rows] == [
        {k: v for k, v in s.model_dump().items() if k != "video_id"} for s in incoming
    ]


def _save_segments(
    session: Session,
    incoming: list[EditorSegmentIn],
    *,
    module_id: int | None = None,
    review_objective_id: int | None = None,
) -> bool:
    """Make the home's segments exactly `incoming`, in order, and place the videos they name.
    Returns whether the list changed (so the home is marked as edited only then)."""
    home = (
        Segment.module_id == module_id
        if module_id is not None
        else Segment.review_objective_id == review_objective_id
    )
    rows = _segment_rows(session, home)
    existing = {s.id: s for s in rows}
    if unknown := sorted({s.id for s in incoming if s.id is not None} - set(existing)):
        where = f"module {module_id}" if module_id is not None else "this review path"
        raise ContentProblem(f"Segments {unknown} are not in {where}.")
    for s in incoming:
        if s.video_id is not None and s.kind != "video":
            raise ContentProblem(f"Segment “{s.title}”: only a video segment plays a video.")
        if s.video_id is not None and session.get(Video, s.video_id) is None:
            raise ContentProblem(f"Segment “{s.title}”: there is no video {s.video_id}.")
    changed = not (
        [s.id for s in incoming] == [r.id for r in rows] and _same_segments(rows, incoming)
    )

    if changed:
        kept = {s.id for s in incoming if s.id is not None}
        if gone := [i for i in existing if i not in kept]:
            session.execute(update(Video).where(Video.segment_id.in_(gone)).values(segment_id=None))
            session.execute(delete(Segment).where(Segment.id.in_(gone)))
        next_id = _next_id(session, Segment.id)
        for position, s in enumerate(incoming, start=1):
            seg_id = s.id
            if seg_id is None:
                seg_id, next_id = next_id, next_id + 1
            # Check it as a fixture segment first: kind rules, a body where one is needed.
            checked = _fixture(
                SegmentFixture,
                {
                    "id": seg_id,
                    **{k: v for k, v in s.model_dump().items() if k not in ("id", "video_id")},
                },
            )
            row = existing.get(seg_id) or Segment(id=seg_id)
            row.module_id = module_id
            row.review_objective_id = review_objective_id
            row.position = position
            row.kind = checked.kind
            row.title = checked.title
            row.body = checked.body
            row.activity_id = checked.activity_id
            row.skip_check_activity_id = checked.skip_check_activity_id
            row.refresher_for = checked.refresher_for
            session.add(row)
            s.id = seg_id
        session.flush()

    # Videos: each video segment plays the video it names (one segment per video).
    for s in incoming:
        if s.kind != "video":
            continue
        current = session.scalar(select(Video).where(Video.segment_id == s.id))
        if current is not None and current.id != s.video_id:
            current.segment_id = None
            session.flush()
        if s.video_id is not None:
            video = session.get_one(Video, s.video_id)
            video.segment_id = s.id
    session.flush()
    return changed


# --- Modules -----------------------------------------------------------------------------------


def _module_out(session: Session, m: Module) -> EditorModuleOut:
    return EditorModuleOut(
        id=m.id,
        slug=m.slug,
        title=m.title,
        goals=m.goals,
        estimated_minutes=m.estimated_minutes,
        segments=_segments_out(session, _segment_rows(session, Segment.module_id == m.id)),
        edited=m.edited_at is not None,
        segments_edited=m.segments_edited_at is not None,
        in_repository=m.id in _repo_ids()["modules"],
    )


def get_module(session: Session, module_id: int) -> EditorModuleOut:
    m = session.get(Module, module_id)
    if m is None:
        raise NotFound(f"There is no module {module_id}.")
    return _module_out(session, m)


def save_module(session: Session, module_id: int | None, data: EditorModuleIn) -> EditorModuleOut:
    """Create a module (`module_id` None: the next number, last in the course) or change one:
    its details and its whole list of segments, in order."""
    if module_id is None:
        top = session.scalar(select(func.max(Module.id)))
        new_id = 0 if top is None else top + 1
        m = Module(id=new_id, position=new_id)  # added once its fields are set
        created = True
    else:
        found = session.get(Module, module_id)
        if found is None:
            raise NotFound(f"There is no module {module_id}.")
        m, created = found, False
    details = data.model_dump(exclude={"segments"})
    checked = _fixture(ModuleFixture, {"id": m.id, **details})
    if session.scalar(select(Module.id).where(Module.slug == checked.slug, Module.id != m.id)):
        raise ContentProblem(f"Another module already uses the slug “{checked.slug}”.")
    before = (m.slug, m.title, m.goals, m.estimated_minutes)
    m.slug, m.title, m.goals = checked.slug, checked.title, checked.goals
    m.estimated_minutes = checked.estimated_minutes
    session.add(m)
    if created or before != (m.slug, m.title, m.goals, m.estimated_minutes):
        m.edited_at = _now()
    session.flush()
    if _save_segments(session, data.segments, module_id=m.id) or created:
        m.segments_edited_at = _now()
    _commit(session)
    return _module_out(session, m)


def delete_module(session: Session, module_id: int) -> None:
    """Delete a module made in the portal, once it is empty and nobody has started it. One from
    the repository can't be deleted: the next seed would bring it back."""
    m = session.get(Module, module_id)
    if m is None:
        raise NotFound(f"There is no module {module_id}.")
    if module_id in _repo_ids()["modules"]:
        raise Conflict(
            "This module comes from the repository, so the next deploy would bring it back. "
            "Take it out of the repository's fixtures instead."
        )
    if session.scalar(select(Segment.id).where(Segment.module_id == module_id).limit(1)):
        raise Conflict("Remove the module's segments first.")
    if session.scalar(select(Activity.id).where(Activity.module_id == module_id).limit(1)):
        raise Conflict("Some activities still belong to this module. Move or delete them first.")
    if session.scalar(
        select(ModuleProgress.id).where(ModuleProgress.module_id == module_id).limit(1)
    ):
        raise Conflict("Students have started this module, so it can't be deleted.")
    session.delete(m)
    _commit(session)


# --- Review paths ------------------------------------------------------------------------------


def get_review_path(session: Session, objective_id: int) -> EditorReviewPathOut:
    o = session.get(Objective, objective_id)
    if o is None:
        raise NotFound(f"There is no objective {objective_id}.")
    rows = _segment_rows(session, Segment.review_objective_id == objective_id)
    return EditorReviewPathOut(
        objective_id=objective_id,
        segments=_segments_out(session, rows),
        edited=o.segments_edited_at is not None,
        in_repository=objective_id in _repo_ids()["review_paths"],
    )


def save_review_path(
    session: Session, objective_id: int, segments: list[EditorSegmentIn]
) -> EditorReviewPathOut:
    o = session.get(Objective, objective_id)
    if o is None:
        raise NotFound(f"There is no objective {objective_id}.")
    if segments:
        # The path's own rules (it starts by teaching again, no refreshers) before anything else.
        _fixture(
            ReviewPathFixture,
            {
                "objective_id": objective_id,
                "segments": [
                    {"id": s.id or 0, **s.model_dump(exclude={"id", "video_id"})} for s in segments
                ],
            },
        )
    if _save_segments(session, segments, review_objective_id=objective_id):
        o.segments_edited_at = _now()
    _commit(session)
    return get_review_path(session, objective_id)


# --- Activities --------------------------------------------------------------------------------


def _activity_row(session: Session, activity_id: int) -> Activity:
    a = session.get(Activity, activity_id)
    if a is None:
        raise NotFound(f"There is no activity {activity_id}.")
    if activity_id in _checkpoint_ids(session):
        raise Conflict("This is a video checkpoint's question. Edit it in the video editor.")
    return a


def _in_use(session: Session, activity_id: int) -> bool:
    return any(
        session.scalar(select(child.id).where(child.activity_id == activity_id).limit(1))
        for child in (Attempt, HintView)
    )


def _shown_in(session: Session, activity_id: int) -> list[str]:
    rows = session.scalars(
        select(Segment)
        .where(
            (Segment.activity_id == activity_id) | (Segment.skip_check_activity_id == activity_id)
        )
        .order_by(Segment.id)
    )
    return [
        f"module {s.module_id}: {s.title}"
        if s.module_id is not None
        else f"review path {s.review_objective_id}: {s.title}"
        for s in rows
    ]


def get_activity(session: Session, activity_id: int) -> EditorActivityOut:
    a = _activity_row(session, activity_id)
    data = _activity_fixture(session, a)
    return EditorActivityOut(
        **{k: v for k, v in data.items() if k != "hints"},
        hints=data["hints"],
        edited=a.edited_at is not None,
        in_repository=a.id in _repo_ids()["activities"],
        in_use=_in_use(session, a.id),
        shown_in=_shown_in(session, a.id),
    )


def save_activity(
    session: Session, activity_id: int | None, data: EditorActivityIn
) -> EditorActivityOut:
    """Create an activity (`activity_id` None) or replace one, hints included. Students' earlier
    attempts keep the result they were given."""
    if activity_id is None:
        a = Activity(id=_next_id(session, Activity.id))
        session.add(a)
    else:
        a = _activity_row(session, activity_id)
    checked = _fixture(ActivityFixture, {"id": a.id, **data.model_dump()})
    for field in ("kind", "title", "visible", "module_id", "objective_id", "purpose"):
        setattr(a, field, getattr(checked, field))
    a.config, a.solution = checked.config, checked.solution
    a.edited_at = _now()
    session.flush()
    session.execute(delete(Hint).where(Hint.activity_id == a.id))
    session.add_all(Hint(activity_id=a.id, level=h.level, body=h.body) for h in checked.hints)
    _commit(session)
    return get_activity(session, a.id)


def delete_activity(session: Session, activity_id: int) -> bool:
    """Delete an activity no segment shows. One students have used, or one from the repository
    (the next seed would bring it back), is taken out of use instead: hidden, in no module, for
    no objective. Returns whether the row was deleted."""
    a = _activity_row(session, activity_id)
    if shown := _shown_in(session, activity_id):
        raise Conflict(f"Take it out of these segments first: {'; '.join(shown)}.")
    if _in_use(session, activity_id) or activity_id in _repo_ids()["activities"]:
        a.visible = False
        a.module_id = None
        a.objective_id = None
        a.purpose = "practice"
        a.edited_at = _now()
        _commit(session)
        return False
    session.execute(delete(Hint).where(Hint.activity_id == activity_id))
    session.delete(a)
    _commit(session)
    return True


# --- Graphs ------------------------------------------------------------------------------------


def get_graph(session: Session, graph_id: int) -> EditorGraphOut:
    g = session.get(GraphScenario, graph_id)
    if g is None:
        raise NotFound(f"There is no graph {graph_id}.")
    return EditorGraphOut(
        id=g.id,
        name=g.name,
        directed=g.directed,
        vertices=g.vertices,
        edges=g.edges,
        start_vertex=g.start_vertex,
        edited=g.edited_at is not None,
        in_repository=g.id in _repo_ids()["graphs"],
    )


def save_graph(session: Session, graph_id: int | None, data: EditorGraphIn) -> EditorGraphOut:
    """Create a graph scenario (`graph_id` None) or change one. It is run through the BFS engine
    first, so the visualiser can always open it."""
    if graph_id is None:
        g = GraphScenario(id=_next_id(session, GraphScenario.id))
        session.add(g)
    else:
        found = session.get(GraphScenario, graph_id)
        if found is None:
            raise NotFound(f"There is no graph {graph_id}.")
        g = found
    checked = _fixture(GraphFixture, {"id": g.id, **data.model_dump()})
    g.name, g.directed, g.vertices = checked.name, checked.directed, checked.vertices
    g.edges = [e.model_dump() for e in checked.edges]
    g.start_vertex = checked.start_vertex
    g.edited_at = _now()
    _commit(session)
    return get_graph(session, g.id)


def delete_graph(session: Session, graph_id: int) -> None:
    g = session.get(GraphScenario, graph_id)
    if g is None:
        raise NotFound(f"There is no graph {graph_id}.")
    if graph_id in _repo_ids()["graphs"]:
        raise Conflict(
            "This graph comes from the repository, so the next deploy would bring it back."
        )
    session.delete(g)
    _commit(session)


# --- Back to the repository --------------------------------------------------------------------

# What "Use the repository's version" clears for each kind of item.
_RESETS: dict[str, Callable[[Session, int], bool]] = {}


def _reset(kind: str) -> Callable[[Callable[[Session, int], bool]], Callable[[Session, int], bool]]:
    def register(fn: Callable[[Session, int], bool]) -> Callable[[Session, int], bool]:
        _RESETS[kind] = fn
        return fn

    return register


@_reset("objectives")
def _reset_objective(session: Session, item_id: int) -> bool:
    o = session.get(Objective, item_id)
    if o is None:
        return False
    o.edited_at = None
    return True


@_reset("modules")
def _reset_module(session: Session, item_id: int) -> bool:
    m = session.get(Module, item_id)
    if m is None:
        return False
    m.edited_at = m.segments_edited_at = None
    return True


@_reset("review_paths")
def _reset_review_path(session: Session, item_id: int) -> bool:
    o = session.get(Objective, item_id)
    if o is None:
        return False
    o.segments_edited_at = None
    return True


@_reset("activities")
def _reset_activity(session: Session, item_id: int) -> bool:
    a = session.get(Activity, item_id)
    if a is None or item_id in _checkpoint_ids(session):
        return False
    a.edited_at = None
    return True


@_reset("graphs")
def _reset_graph(session: Session, item_id: int) -> bool:
    g = session.get(GraphScenario, item_id)
    if g is None:
        return False
    g.edited_at = None
    return True


def use_repository_version(session: Session, kind: str, item_id: int) -> None:
    """Drop the portal's edit of one item and load the repository's version of it now (the seed,
    for that item: everything else nobody edited is refreshed too, as on a deploy)."""
    if item_id not in _repo_ids()[kind]:
        raise Conflict("The repository has no version of this. It was made in the portal.")
    if not _RESETS[kind](session, item_id):
        raise NotFound("It no longer exists.")
    session.flush()
    try:
        load(session)
    except ValueError as exc:
        session.rollback()
        raise ContentProblem(str(exc)) from exc
    try:
        check_database(session)
    except ContentProblem as exc:
        # load committed; undo by marking it edited again is not possible, so say what broke.
        raise ContentProblem(
            f"The repository's version is back, but the content now has a problem: {exc}"
        ) from exc


# --- Export ------------------------------------------------------------------------------------


def _dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_defaults=True)


def _json(data: dict[str, Any]) -> bytes:
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def export_fixtures(session: Session) -> bytes:
    """The database's content as fixture files, zipped, laid out as api/app/seed is: unzip them
    there, check the diff and commit, and the repository matches the portal. Checkpoint
    questions are left out (they belong to videos: use the video export), and so are activities
    the fixtures dropped and nobody edited."""
    content = check_database(session)
    repo = _repo_ids()["activities"]
    checkpoints = _checkpoint_ids(session)
    edited = set(session.scalars(select(Activity.id).where(Activity.edited_at.is_not(None))))
    on_paths = {s.activity_id for r in content.review_paths for s in r.segments if s.activity_id}
    activities = [
        a
        for a in content.activities
        if a.id not in checkpoints
        and a.id < EDITOR_IDS_FROM
        and (a.module_id is not None or a.id in on_paths or a.id in repo or a.id in edited)
    ]
    files: dict[str, dict[str, Any]] = {
        "objectives.json": {"objectives": [_dump(o) for o in content.objectives]},
        "graphs.json": {"graphs": [_dump(g) for g in content.graphs]},
    }
    for m in content.modules:
        files[f"module-{m.id}.json"] = {
            "modules": [_dump(m)],
            "activities": [_dump(a) for a in activities if a.module_id == m.id],
        }
    rest = [a for a in activities if a.module_id is None]
    files["review.json"] = {
        "review_paths": [_dump(r) for r in content.review_paths],
        "activities": [_dump(a) for a in rest],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, _json(data))
    return buffer.getvalue()
