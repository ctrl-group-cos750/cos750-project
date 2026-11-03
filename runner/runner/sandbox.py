"""Runs one submission in its own process, under the limits of NFR-S7, and grades it.

The process is `python -I -B harness.py` in a fresh temporary directory, with an empty
environment and its own session, so the whole group can be killed. The harness sets the CPU,
memory, output, process and file limits on itself before any student code runs; this side
enforces the wall-clock limit and reads the harness's report. Stdout and stderr go to files, so the
output limit is the kernel's file-size limit and output never fills the runner's memory.
"""

import contextlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

from runner.models import Outcome, RunResult, TestCase, TestResult

HARNESS = Path(__file__).with_name("harness.py")
MIB = 1024 * 1024


@dataclass(frozen=True)
class Limits:
    cpu_seconds: int = 3
    wall_seconds: float = 10
    memory_bytes: int = 128 * MIB
    output_bytes: int = 1 * MIB


LIMITS = Limits()

MESSAGES: dict[Outcome, str] = {
    "timeout": "Your code took longer than {cpu} seconds. Check for a loop that never ends.",
    "memory_limit": "Your code used more than {memory} MB of memory. Check for a list or a loop "
    "that keeps growing.",
    "output_limit": "Your code printed more than {output} MB. Check for a print inside a loop "
    "that never ends.",
    "crashed": "Your code stopped Python before the tests finished. Very deep recursion, or "
    "ending the program on purpose, can do this.",
}


def _work_root() -> str:
    """Where each run gets its folder. In the container /tmp is the only writable place.

    Each run's folder stays empty: its output files have no name (see execute), and every run is
    non-dumpable, so another run (the same user) finds nothing to read.
    """
    root = Path(os.environ.get("RUNNER_TMP") or tempfile.gettempdir()) / "runs"
    root.mkdir(mode=0o711, exist_ok=True)
    root.chmod(0o711)
    return str(root)


# NUL: Postgres refuses it in text and jsonb, so none goes back to the API, which may store it.
_NUL, _REPLACEMENT = chr(0), chr(0xFFFD)


def clean(text: str) -> str:
    return text.replace(_NUL, _REPLACEMENT)


def _read_capped(file: IO[bytes], limit: int) -> str:
    file.seek(0)
    return clean(file.read(limit).decode("utf-8", errors="replace"))


def _read_events(fd: int, limit: int, events: list[dict[str, Any]], ready: threading.Event) -> None:
    """Reads the harness's JSON lines until it closes the pipe, keeping at most `limit` bytes."""
    seen = 0
    with os.fdopen(fd, "rb") as pipe:
        for line in pipe:
            if not ready.is_set() and line.strip() == b'{"event": "ready"}':
                ready.set()
                continue
            seen += len(line)
            if seen > limit:
                break
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict):
                events.append(event)


def execute(code: str, tests: list[TestCase], limits: Limits = LIMITS) -> RunResult:
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="run-", dir=_work_root()) as work_dir:
        work = Path(work_dir)
        read_fd, write_fd = os.pipe()
        job = {
            "code": code,
            # Everything but the expected answers, which stay in this process.
            "tests": [t.model_dump(include={"kind", "call", "code"}) for t in tests],
            "limits": {
                "cpu_seconds": limits.cpu_seconds,
                "memory_bytes": limits.memory_bytes,
                "output_bytes": limits.output_bytes,
            },
        }
        env = {
            "RESULT_FD": str(write_fd),
            "RUNNER_PID": str(os.getpid()),
            "HOME": work_dir,
            "LANG": "C.UTF-8",
            "PATH": "/usr/bin",
        }
        # Output files with no name (O_TMPFILE): only this process and the run hold them, so
        # another run can't open them, and nothing is left behind.
        with tempfile.TemporaryFile(dir=work) as out, tempfile.TemporaryFile(dir=work) as err:
            proc = subprocess.Popen(
                [sys.executable, "-I", "-B", str(HARNESS)],
                stdin=subprocess.PIPE,
                stdout=out,
                stderr=err,
                pass_fds=(write_fd,),
                cwd=work_dir,
                env=env,
                start_new_session=True,
            )
            os.close(write_fd)
            events: list[dict[str, Any]] = []
            ready = threading.Event()
            reader = threading.Thread(
                target=_read_events, args=(read_fd, limits.output_bytes, events, ready)
            )
            reader.start()
            if proc.stdin is None:
                raise RuntimeError("the harness has no stdin")
            # The job only once the harness is non-dumpable, so no other run can read it.
            if ready.wait(timeout=limits.wall_seconds):
                with contextlib.suppress(BrokenPipeError):  # the harness died before reading it
                    proc.stdin.write(json.dumps(job).encode())
            with contextlib.suppress(BrokenPipeError):
                proc.stdin.close()
            returncode, cpu_used, timed_out = _wait(proc, started + limits.wall_seconds)
            reader.join(timeout=5)
            stdout_size, stderr_size = (
                os.fstat(out.fileno()).st_size,
                os.fstat(err.fileno()).st_size,
            )
            stdout = _read_capped(out, limits.output_bytes)
            stderr = _read_capped(err, limits.output_bytes)

    outcome = _outcome(
        returncode,
        timed_out or cpu_used >= limits.cpu_seconds,
        events,
        output_full=max(stdout_size, stderr_size) >= limits.output_bytes,
    )
    message = _message(outcome, events, limits)
    return RunResult(
        outcome=outcome,
        message=clean(message) if message else None,
        tests=[
            t.model_copy(update={"message": clean(t.message) if t.message else None})
            for t in _grade(tests, events)
        ],
        stdout=stdout,
        stderr=stderr,
        duration_ms=int((time.monotonic() - started) * 1000),
    )


def _wait(proc: subprocess.Popen[bytes], deadline: float) -> tuple[int, float, bool]:
    """Waits for the process until the wall-clock deadline, then kills its whole group.

    Returns its exit code, the CPU seconds it used and whether it ran out of time. os.wait4 gives
    this process's own CPU time, so a run killed for using too much CPU is reported as a time-out,
    not mistaken for running out of memory.
    """
    timed_out = False
    while True:
        pid, status, usage = os.wait4(proc.pid, os.WNOHANG)
        if pid:
            break
        if time.monotonic() >= deadline:
            timed_out = True
            os.killpg(proc.pid, signal.SIGKILL)
            pid, status, usage = os.wait4(proc.pid, 0)
            break
        time.sleep(0.01)
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)  # anything it left behind in its group
    proc.returncode = os.waitstatus_to_exitcode(status)  # reaped here; Popen mustn't wait again
    return proc.returncode, usage.ru_utime + usage.ru_stime, timed_out


def _kind(events: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    return next((e for e in events if e.get("event") == name), None)


def _outcome(
    returncode: int, timed_out: bool, events: list[dict[str, Any]], output_full: bool
) -> Outcome:
    killed_by = -returncode if returncode < 0 else 0
    if timed_out or killed_by == signal.SIGXCPU:
        return "timeout"
    if killed_by == signal.SIGXFSZ or output_full:
        return "output_limit"
    if _kind(events, "memory") or killed_by == signal.SIGKILL:  # SIGKILL here: out of memory
        return "memory_limit"
    if _kind(events, "syntax_error"):
        return "syntax_error"
    if _kind(events, "error"):
        return "error"
    if _kind(events, "done"):
        return "completed"
    return "crashed"


def _message(outcome: Outcome, events: list[dict[str, Any]], limits: Limits) -> str | None:
    if outcome == "completed":
        return None
    if outcome == "syntax_error":
        e = _kind(events, "syntax_error") or {}
        return f"Python couldn't read your code: {e.get('message')} (line {e.get('line')})."
    if outcome == "error":
        e = _kind(events, "error") or {}
        where = f" on line {e['line']}" if e.get("line") else ""
        return f"Your code raised {e.get('type')}{where}: {e.get('message')}"
    return MESSAGES[outcome].format(
        cpu=limits.cpu_seconds,
        memory=limits.memory_bytes // MIB,
        output=limits.output_bytes // MIB,
    )


def _grade(tests: list[TestCase], events: list[dict[str, Any]]) -> list[TestResult]:
    by_test = {e["test"]: e for e in events if isinstance(e.get("test"), int)}
    results = []
    for i, test in enumerate(tests):
        event = by_test.get(i)
        if event is None:
            results.append(
                TestResult(
                    name=test.name, passed=False, message="Not run: your code stopped first."
                )
            )
        elif event["event"] == "value":
            passed = event.get("value") == test.expected
            detail = None
            if not passed:
                detail = test.message or (
                    f"{test.call} returned {json.dumps(event.get('value'))}, "
                    f"expected {json.dumps(test.expected)}."
                    if test.visible
                    else "This test didn't pass."
                )
            results.append(TestResult(name=test.name, passed=passed, message=detail))
        elif event["event"] == "passed":
            results.append(TestResult(name=test.name, passed=True))
        else:
            if test.message:
                detail = test.message
            elif test.visible:
                text = f": {event.get('message')}" if event.get("message") else ""
                detail = f"{event.get('type')}{text}"
            else:
                detail = f"Your code raised {event.get('type')} on this test."
            results.append(TestResult(name=test.name, passed=False, message=detail))
    return results
