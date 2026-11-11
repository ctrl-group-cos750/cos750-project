"""The staff content editor (staff portal: /staff/content): objectives, modules and their
segments, review paths, activities with their hints, and graph scenarios.

Content lives in the database. The fixtures in app/seed fill it on a fresh deploy and refresh what
nobody has edited; once staff change an item here, the seed leaves it alone (app/seed, `load`).
Every save is checked with the same rules CI applies to the fixtures, so the portal can't store
content a student would trip over (NFR-M5). See app/services/content_editor.py.
"""

from collections.abc import Callable
from typing import Any, Literal, TypeVar

from fastapi import APIRouter, HTTPException, Response, status

from app.auth import StaffUser
from app.db import DbSession
from app.schemas.staff_content import (
    EditorActivityIn,
    EditorActivityOut,
    EditorContentOverview,
    EditorDeleteResult,
    EditorGraphIn,
    EditorGraphOut,
    EditorModuleIn,
    EditorModuleOut,
    EditorObjectiveIn,
    EditorObjectiveOut,
    EditorReviewPathIn,
    EditorReviewPathOut,
)
from app.services import content_editor as editor
from app.services.content_editor import Conflict, ContentProblem, NotFound

router = APIRouter(prefix="/api/staff/content", tags=["staff content"])

T = TypeVar("T")
Responses = dict[int | str, dict[str, Any]]
MISSING: Responses = {status.HTTP_404_NOT_FOUND: {"description": "No such item."}}
CONFLICT: Responses = {
    status.HTTP_409_CONFLICT: {"description": "Not possible here; the message says why."}
}


def _run(action: Callable[[], T]) -> T:  # noqa: UP047 (the dev container has Python 3.11)
    """Run an editor action, turning its errors into the HTTP status the editor shows."""
    try:
        return action()
    except NotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Conflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ContentProblem as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get("")
def content_overview(session: DbSession, _staff: StaffUser) -> EditorContentOverview:
    """Everything the editor lists: objectives, modules, review paths, activities (not the video
    checkpoints' questions), graphs, and the videos a video segment can play."""
    return editor.overview(session)


@router.get(
    "/export", response_class=Response, responses={200: {"content": {"application/zip": {}}}}
)
def export_content(session: DbSession, _staff: StaffUser) -> Response:
    """The content as fixture files (a zip laid out like api/app/seed), to commit to the
    repository so a fresh database is seeded with what the portal holds now."""
    data = _run(lambda: editor.export_fixtures(session))
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="content-fixtures.zip"'},
    )


# --- Objectives


@router.post("/objectives", status_code=status.HTTP_201_CREATED)
def create_objective(
    data: EditorObjectiveIn, session: DbSession, _staff: StaffUser
) -> EditorObjectiveOut:
    """Add the next objective (up to 8: each has a badge)."""
    return _run(lambda: editor.save_objective(session, None, data))


@router.put("/objectives/{objective_id}", responses=MISSING)
def update_objective(
    objective_id: int, data: EditorObjectiveIn, session: DbSession, _staff: StaffUser
) -> EditorObjectiveOut:
    """Change an objective's wording or its mastery rule. Every student's result is worked out
    again with the new rule."""
    return _run(lambda: editor.save_objective(session, objective_id, data))


# --- Modules


@router.get("/modules/{module_id}", responses=MISSING)
def get_module(module_id: int, session: DbSession, _staff: StaffUser) -> EditorModuleOut:
    return _run(lambda: editor.get_module(session, module_id))


@router.post("/modules", status_code=status.HTTP_201_CREATED)
def create_module(data: EditorModuleIn, session: DbSession, _staff: StaffUser) -> EditorModuleOut:
    """Add a module after the last one."""
    return _run(lambda: editor.save_module(session, None, data))


@router.put("/modules/{module_id}", responses=MISSING)
def update_module(
    module_id: int, data: EditorModuleIn, session: DbSession, _staff: StaffUser
) -> EditorModuleOut:
    """Replace a module's details and its segments, in order. Keep each existing segment's `id`;
    leave it out for a new one. A segment left out is removed."""
    return _run(lambda: editor.save_module(session, module_id, data))


@router.delete(
    "/modules/{module_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**MISSING, **CONFLICT},
)
def delete_module(module_id: int, session: DbSession, _staff: StaffUser) -> None:
    """Delete an empty module made in the portal that no student has started."""
    _run(lambda: editor.delete_module(session, module_id))


# --- Review paths


@router.get("/review-paths/{objective_id}", responses=MISSING)
def get_review_path(
    objective_id: int, session: DbSession, _staff: StaffUser
) -> EditorReviewPathOut:
    return _run(lambda: editor.get_review_path(session, objective_id))


@router.put("/review-paths/{objective_id}", responses=MISSING)
def update_review_path(
    objective_id: int, data: EditorReviewPathIn, session: DbSession, _staff: StaffUser
) -> EditorReviewPathOut:
    """Replace the objective's review path: its segments, in order."""
    return _run(lambda: editor.save_review_path(session, objective_id, data.segments))


# --- Activities


@router.get("/activities/{activity_id}", responses={**MISSING, **CONFLICT})
def get_activity(activity_id: int, session: DbSession, _staff: StaffUser) -> EditorActivityOut:
    return _run(lambda: editor.get_activity(session, activity_id))


@router.post("/activities", status_code=status.HTTP_201_CREATED)
def create_activity(
    data: EditorActivityIn, session: DbSession, _staff: StaffUser
) -> EditorActivityOut:
    """Add an activity. A segment shows it once a module or review path lists it."""
    return _run(lambda: editor.save_activity(session, None, data))


@router.put("/activities/{activity_id}", responses={**MISSING, **CONFLICT})
def update_activity(
    activity_id: int, data: EditorActivityIn, session: DbSession, _staff: StaffUser
) -> EditorActivityOut:
    """Replace an activity and its hints. Earlier attempts keep the result they were given."""
    return _run(lambda: editor.save_activity(session, activity_id, data))


@router.delete("/activities/{activity_id}", responses={**MISSING, **CONFLICT})
def delete_activity(activity_id: int, session: DbSession, _staff: StaffUser) -> EditorDeleteResult:
    """Delete an activity no segment shows. One students have used, or one from the repository,
    is taken out of use instead (`deleted: false`)."""
    return EditorDeleteResult(deleted=_run(lambda: editor.delete_activity(session, activity_id)))


# --- Graphs


@router.get("/graphs/{graph_id}", responses=MISSING)
def get_graph(graph_id: int, session: DbSession, _staff: StaffUser) -> EditorGraphOut:
    return _run(lambda: editor.get_graph(session, graph_id))


@router.post("/graphs", status_code=status.HTTP_201_CREATED)
def create_graph(data: EditorGraphIn, session: DbSession, _staff: StaffUser) -> EditorGraphOut:
    return _run(lambda: editor.save_graph(session, None, data))


@router.put("/graphs/{graph_id}", responses=MISSING)
def update_graph(
    graph_id: int, data: EditorGraphIn, session: DbSession, _staff: StaffUser
) -> EditorGraphOut:
    return _run(lambda: editor.save_graph(session, graph_id, data))


@router.delete(
    "/graphs/{graph_id}", status_code=status.HTTP_204_NO_CONTENT, responses={**MISSING, **CONFLICT}
)
def delete_graph(graph_id: int, session: DbSession, _staff: StaffUser) -> None:
    """Delete a graph made in the portal."""
    _run(lambda: editor.delete_graph(session, graph_id))


# --- Back to the repository

ItemKind = Literal["objectives", "modules", "review-paths", "activities", "graphs"]


@router.post(
    "/{kind}/{item_id}/use-repository",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**MISSING, **CONFLICT},
)
def use_repository_version(
    kind: ItemKind, item_id: int, session: DbSession, _staff: StaffUser
) -> None:
    """Drop the portal's edit of this item and load the repository's version of it now."""
    _run(lambda: editor.use_repository_version(session, kind.replace("-", "_"), item_id))
