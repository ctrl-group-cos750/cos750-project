import asyncio
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import RequestResponseEndpoint
from starlette.staticfiles import StaticFiles

from app.db import engine
from app.media import media_dir
from app.routers import (
    activities,
    auth,
    events,
    graphs,
    mastery,
    modules,
    profile,
    rewards,
    staff,
    staff_accounts,
    staff_evaluation,
    videos,
)

# Every route lives under /api: nginx in the web container forwards that prefix here unchanged.


def docs_urls(setting: str | None) -> dict[str, str | None]:
    """The interactive docs and the schema are on unless API_DOCS is "off" (production)."""
    on = (setting or "on").strip().lower() != "off"
    return {
        "docs_url": "/api/docs" if on else None,
        "openapi_url": "/api/openapi.json" if on else None,
        "redoc_url": None,
    }


_docs = docs_urls(os.environ.get("API_DOCS"))
app = FastAPI(
    title="Ctrl Academy API",
    docs_url=_docs["docs_url"],
    openapi_url=_docs["openapi_url"],
    redoc_url=_docs["redoc_url"],
)
app.include_router(auth.router)
app.include_router(activities.router)
app.include_router(events.router)
app.include_router(graphs.router)
app.include_router(rewards.router)
app.include_router(mastery.router)
app.include_router(profile.router)
app.include_router(modules.router)
app.include_router(videos.router)
app.include_router(staff.router)
app.include_router(staff_accounts.router)
app.include_router(staff_evaluation.router)

# Development without Docker only: serve uploads at /media/ from MEDIA_DIR, which Vite's dev
# server proxies here. In Docker, nginx serves the media volume and this stays off.
if os.environ.get("SERVE_MEDIA") == "1":
    app.mount("/media", StaticFiles(directory=media_dir(), check_dir=False), name="media")


# Admission control. A request takes its database connection in one thread job and runs its handler
# in another, so it can hold a connection while it waits for a thread. Under a burst, requests held
# every connection while every thread waited for one, and the API stalled for minutes (stress test,
# 2 Nov 2026). At most MAX_IN_FLIGHT requests run at once, fewer than the 40 threads and the 50
# connections (app/db.py), so that can't happen. The rest wait here, holding neither; one that waits
# QUEUE_WAIT seconds gets a quick 503 instead of joining a pile-up.
MAX_IN_FLIGHT = 30
QUEUE_WAIT = 5.0
_in_flight = asyncio.Semaphore(MAX_IN_FLIGHT)
BUSY = "Ctrl Academy is busy. Try again in a moment."


@app.middleware("http")
async def admission(request: Request, call_next: RequestResponseEndpoint) -> Response:
    # The health check takes and returns its connection within one thread, and Docker's health
    # check must still get an answer when the API is busy.
    if request.url.path == "/api/health":
        return await call_next(request)
    try:
        await asyncio.wait_for(_in_flight.acquire(), timeout=QUEUE_WAIT)
    except TimeoutError:
        return JSONResponse(status_code=503, content={"detail": BUSY}, headers={"Retry-After": "2"})
    try:
        return await call_next(request)
    finally:
        _in_flight.release()


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
    errors = [
        {"loc": list(e["loc"]), "msg": e["msg"].removeprefix("Value error, "), "type": e["type"]}
        for e in exc.errors()
    ]
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
