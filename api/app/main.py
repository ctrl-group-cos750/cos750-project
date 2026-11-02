from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import RequestResponseEndpoint

from app.db import engine
from app.routers import auth

# Every route lives under /api: nginx in the web container forwards that prefix here unchanged.
app = FastAPI(title="Ctrl Academy API", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.include_router(auth.router)


@app.middleware("http")
async def no_store(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """API answers are about one student and change all the time: no browser or proxy keeps them."""
    response = await call_next(request)
    response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Says which fields are wrong and why, without repeating what was sent.

    FastAPI's default echoes each bad input back. That repeats a rejected password, and for JSON
    nested thousands deep its encoder recursed until the request failed with 500 (found by
    scripts/security-probe.py on staging).
    """
    errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


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
