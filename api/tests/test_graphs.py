"""The graph-scenario endpoints end to end (HTTP + database): the scenario is returned for the
visualiser and its BFS steps are computed by the one tested engine (FR-6.1, FR-6.5)."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import GraphScenario

STUDENT = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}

DIAMOND: dict[str, Any] = {
    "name": "Diamond",
    "directed": False,
    "vertices": ["A", "B", "C", "D"],
    "edges": [
        {"source": "A", "target": "B"},
        {"source": "A", "target": "C"},
        {"source": "B", "target": "D"},
        {"source": "C", "target": "D"},
    ],
    "start_vertex": "A",
}


def make_scenario(db: Session, **data: Any) -> int:
    scenario = GraphScenario(**data)
    db.add(scenario)
    db.commit()
    return scenario.id


def log_in(client: TestClient) -> None:
    assert client.post("/api/auth/register", json=STUDENT).status_code == 201


def test_get_scenario_returns_the_graph(client: TestClient, db: Session) -> None:
    scenario_id = make_scenario(db, **DIAMOND)
    log_in(client)
    res = client.get(f"/api/graphs/{scenario_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Diamond"
    assert body["vertices"] == ["A", "B", "C", "D"]
    assert body["startVertex"] == "A"


def test_get_scenario_requires_a_login(client: TestClient, db: Session) -> None:
    scenario_id = make_scenario(db, **DIAMOND)
    assert client.get(f"/api/graphs/{scenario_id}").status_code == 401


def test_get_bfs_returns_the_level_order_steps(client: TestClient, db: Session) -> None:
    scenario_id = make_scenario(db, **DIAMOND)
    log_in(client)
    res = client.get(f"/api/graphs/{scenario_id}/bfs")
    assert res.status_code == 200
    body = res.json()
    assert body["order"] == ["A", "B", "C", "D"]
    assert len(body["steps"]) == 4
    assert body["steps"][0]["visitedVertex"] == "A"
    assert body["steps"][0]["discovered"] == ["B", "C"]
    # D is discovered by B, the first to reach it, and not again by C.
    assert body["steps"][2]["discovered"] == []


def test_get_bfs_requires_a_login(client: TestClient, db: Session) -> None:
    scenario_id = make_scenario(db, **DIAMOND)
    assert client.get(f"/api/graphs/{scenario_id}/bfs").status_code == 401


def test_missing_scenario_is_404(client: TestClient, db: Session) -> None:
    log_in(client)
    assert client.get("/api/graphs/999").status_code == 404
    assert client.get("/api/graphs/999/bfs").status_code == 404


def test_a_scenario_the_engine_rejects_is_422(client: TestClient, db: Session) -> None:
    # A stored scenario whose start vertex is not in the graph: the data is at fault, not the
    # request, and the engine refuses it.
    bad = dict(DIAMOND, start_vertex="Z")
    scenario_id = make_scenario(db, **bad)
    log_in(client)
    res = client.get(f"/api/graphs/{scenario_id}/bfs")
    assert res.status_code == 422
