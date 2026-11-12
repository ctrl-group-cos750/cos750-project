from fastapi import APIRouter, HTTPException, status

from app.auth import CurrentUser
from app.db import DbSession
from app.models import GraphScenario
from app.schemas.graphs import BfsResult, GraphScenarioOut
from app.schemas.ids import RowId
from app.services.bfs import InvalidGraph, run_bfs

router = APIRouter(prefix="/api/graphs", tags=["graphs"])

NOT_FOUND = "This graph scenario does not exist."


def _scenario_out(scenario: GraphScenario) -> GraphScenarioOut:
    """The stored scenario as the engine and the frontend see it. `edges` is validated into
    `GraphEdge`s by GraphScenarioOut, so a malformed stored edge is reported as a 500, not run."""
    return GraphScenarioOut.model_validate(scenario)


def _scenario_or_404(session: DbSession, scenario_id: int) -> GraphScenario:
    scenario = session.get(GraphScenario, scenario_id)
    if scenario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return scenario


@router.get("/{scenario_id}", response_model=GraphScenarioOut)
def get_scenario(scenario_id: RowId, session: DbSession, _user: CurrentUser) -> GraphScenario:
    """The graph scenario to draw (FR-6.1)."""
    return _scenario_or_404(session, scenario_id)


@router.get("/{scenario_id}/bfs")
def get_bfs(scenario_id: RowId, session: DbSession, _user: CurrentUser) -> BfsResult:
    """The breadth-first traversal of the scenario, step by step (FR-6.1).

    Computed by the one tested engine so the animation, prediction and trace table agree (FR-6.5).
    A scenario the engine refuses (bad start vertex, duplicate vertex, edge to an unknown vertex)
    is a 422, since the stored data, not the request, is at fault.
    """
    scenario = _scenario_or_404(session, scenario_id)
    try:
        return run_bfs(_scenario_out(scenario))
    except InvalidGraph as exc:
        raise HTTPException(422, detail=str(exc)) from exc  # constant is deprecated upstream
