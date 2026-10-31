from fastapi.testclient import TestClient
from sqlalchemy import Engine


def test_health_reports_a_working_database(client: TestClient, working_db: Engine) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "database": "ok"}


def test_health_still_answers_when_the_database_is_down(
    client: TestClient, unreachable_db: Engine
) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "database": "unreachable"}


def test_docs_live_under_api(client: TestClient) -> None:
    # nginx only forwards /api/* to this service, so the docs must live there too.
    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/openapi.json").json()["info"]["title"] == "Ctrl Academy API"
    assert client.get("/docs").status_code == 404
