# Code runner

Runs students' Python where it can't harm anything (SE document NFR-S7). An internal service: only
the API can reach it. **It has no network at all** (`network_mode: none`): it listens on the Unix
socket `/run/runner/runner.sock` (`RUNNER_SOCKET`), on a small volume that only the runner and the API
mount. The API's client is `api/app/runner_client.py` (`run_code`, which raises
`RunnerUnavailable` with a message for the student).

## Contract

`POST /run`, JSON in camelCase:

```json
{
  "code": "def bfs(graph, start):\n    ...",
  "tests": [
    { "name": "visits every vertex", "kind": "call",
      "call": "bfs({'A': ['B'], 'B': []}, 'A')", "expected": ["A", "B"],
      "message": "Is every neighbour added to the queue?" },
    { "name": "example", "kind": "code", "visible": true,
      "code": "assert bfs({'A': []}, 'A') == ['A']" }
  ]
}
```

- **`call` tests** (use these for hidden, graded tests): `call` is an expression; the test passes
  when it returns `expected`. Values compare as JSON: tuples as lists, sets as sorted lists. The
  expected answer stays in the runner's own process; the student's code never sees it, so it can't
  read it or fake a pass.
- **`code` tests** (visible examples, tests the student writes): Python that passes when it runs
  without an error, usually asserts. They must be `visible`: a code test reports its own result
  from inside the student's process, where the student's code could fake it, so the runner refuses
  hidden ones (422). Graded, hidden tests are always call tests.
- `visible: true` lets a failure show its details (what came back, the assertion message). A hidden
  test shows only its `message`, or "This test didn't pass."
- Up to 50 tests and 100 kB of code.

Answer:

```json
{
  "outcome": "completed",
  "message": null,
  "tests": [{ "name": "visits every vertex", "passed": true, "message": null }],
  "stdout": "", "stderr": "", "durationMs": 41
}
```

`outcome` is `completed` (see each test), or one of `syntax_error`, `error`, `timeout`,
`memory_limit`, `output_limit` and `crashed`, with `message` saying what happened in words for the
student (FR-5.6), for example "Your code took longer than 3 seconds. Check for a loop that never
ends." Show `message` as it is. When four runs are already going, the answer is
`503 {"detail": "The code runner is busy. Try again in a moment."}` with `Retry-After: 2`.

## Limits and layers

| Layer | What |
|---|---|
| Container (`docker-compose.yml`) | **No network** (`network_mode: none`, only loopback); reached through its socket volume; no secrets or database; read-only filesystem except a 64 MB `/tmp`; unprivileged user; all capabilities dropped; `no-new-privileges`; 2 CPUs, 768 MB (four runs and the runner), 64 processes |
| The rest of the app | Only running code is ever affected: the runner's caps are its own, it has a quarter of the default CPU weight, no swap, and is the first thing killed if the server runs out of memory; the API doesn't wait for it to start |
| Process (`runner/harness.py`, set before any student code runs, as hard limits) | 3 s CPU, 128 MB memory, 1 MB per output file, no new processes or threads, 32 open files |
| Kernel filter (seccomp, in `harness.py`) | No network sockets at all, whatever the Docker network allows; no creating, writing, renaming or deleting files (reading and imports still work), so `/tmp` can't be filled; signals and resource limits only for the run's own process, so it can't kill or cripple the runner or another run; nothing that reaches into other processes (pidfd, ptrace, process_vm, priorities); no calls from another architecture |
| Between runs | Each run is non-dumpable from its first instruction, before its job arrives, so another run can't read its memory, open files or folder through `/proc`; its output files have no name on disk, so there is nothing to open |
| What goes back | NUL characters are replaced in the output and every message, because Postgres would refuse them when the API stores an attempt |
| Runner (`runner/sandbox.py`) | Fresh temporary folder and empty environment per run; 10 s wall clock, then the whole process group is killed; the runner process is non-dumpable, so student code can't read its memory or environment |
| Service (`runner/app.py`) | At most four runs at once |
| API (#21, to build) | One run at a time per student and at most 20 a minute, so one student can't keep every slot busy; wait at most 15 s for the runner; show the 503 "busy" message as it is |

## Checks

- `pytest --cov` in `runner/`: grading, messages and hostile code run directly (at least 90%
  coverage).
- `tests/container_check.py`: hostile code against the real image with the compose limits, from a
  second container that mounts the socket volume. CI runs it on every PR.
- `tests/network_check.py`: runs inside the runner container, outside the sandbox filter, and fails
  unless the container has nothing but loopback. CI runs it on every PR; on staging it runs through
  a Coolify scheduled task.
- `tests/isolation_check.py`: with the whole stack up, measures the app at rest, then while the
  sandbox is flooded with hostile code, then with the runner stopped. CI runs it on every PR.
