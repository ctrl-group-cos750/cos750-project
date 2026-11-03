# Code runner

Runs students' Python where it can't harm anything (SE document NFR-S7). An internal service: only
the API can reach it, at `http://runner:8000` (`RUNNER_URL`).

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
  without an error, usually asserts.
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
| Container (`docker-compose.yml`) | Internal network shared only with the API; no secrets, volumes or database; read-only filesystem except a 64 MB `/tmp`; unprivileged user; all capabilities dropped; `no-new-privileges`; 2 CPUs, 768 MB (four runs and the runner), 64 processes |
| Process (`runner/harness.py`, set before any student code runs, as hard limits) | 3 s CPU, 128 MB memory, 1 MB per output file, no new processes or threads, 32 open files |
| Kernel filter (seccomp, in `harness.py`) | No network sockets at all, whatever the Docker network allows; signals and resource limits only for the run's own process, so it can't kill or cripple the runner or another run; nothing that reaches into other processes (pidfd, ptrace, process_vm, priorities); no calls from another architecture |
| Runner (`runner/sandbox.py`) | Fresh temporary folder and empty environment per run; 10 s wall clock, then the whole process group is killed; the runner process is non-dumpable, so student code can't read its memory or environment |
| Service (`runner/app.py`) | At most four runs at once |
| API (#21, to build) | One run at a time per student and at most 20 a minute, so one student can't keep every slot busy; wait at most 15 s for the runner; show the 503 "busy" message as it is |

## Checks

- `pytest --cov` in `runner/`: grading, messages and hostile code run directly (at least 90%
  coverage).
- `tests/container_check.py`: hostile code against the real image with the compose limits, from a
  second container on the internal network. CI runs it on every PR.
