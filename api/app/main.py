from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import engine

# Every route lives under /api: nginx in the web container forwards that prefix here unchanged.
app = FastAPI(title="Ctrl Academy API", docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.get("/api/health")
def health() -> dict[str, str]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError:
        database = "unreachable"
    return {"status": "ok", "database": database}
