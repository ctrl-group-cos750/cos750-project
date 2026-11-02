from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import engine
from app.routers import auth

# Every route lives under /api: nginx in the web container forwards that prefix here unchanged.
app = FastAPI(title="Ctrl Academy API", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.include_router(auth.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            try:
                schema = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            except SQLAlchemyError:
                schema = None
        database = "ok"
    except SQLAlchemyError:
        database, schema = "unreachable", None
    return {"status": "ok", "database": database, "schema": schema or "none"}
