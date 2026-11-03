"""The code runner's HTTP service (SE document NFR-S7, §9 "Code runner (internal)").

Only the API can reach it: it sits on an internal Docker network with no route to the internet.
It keeps nothing between requests and holds no secrets.
"""

import asyncio
import ctypes
import sys

from anyio import to_thread
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from runner.models import RunRequest, RunResult
from runner.sandbox import execute

MAX_RUNS = 4  # NFR-S7: at most four submissions at a time
BUSY_WAIT = 1.0
BUSY = "The code runner is busy. Try again in a moment."


def protect_this_process() -> bool:
    """Makes this process non-dumpable, so the student code it starts (same user) can't read its
    memory or environment through /proc. That memory holds the expected answers."""
    if not sys.platform.startswith("linux"):
        return False
    pr_set_dumpable = 4
    return bool(ctypes.CDLL(None).prctl(pr_set_dumpable, 0, 0, 0, 0) == 0)


protect_this_process()
app = FastAPI(title="Ctrl Academy code runner", docs_url=None, redoc_url=None, openapi_url=None)
_slots = asyncio.Semaphore(MAX_RUNS)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/run", response_model=RunResult, response_model_by_alias=True)
async def run(request: RunRequest) -> RunResult | JSONResponse:
    try:
        await asyncio.wait_for(_slots.acquire(), timeout=BUSY_WAIT)
    except TimeoutError:
        return JSONResponse(status_code=503, content={"detail": BUSY}, headers={"Retry-After": "2"})
    try:
        return await to_thread.run_sync(execute, request.code, request.tests)
    finally:
        _slots.release()
