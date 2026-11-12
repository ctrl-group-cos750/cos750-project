# Developer Notes — Wave 1: module-5.json content fixture

## Files Created

_(none — module-5.json already existed as a near-empty stub)_

## Files Modified

- `api/app/seed/module-5.json` — filled with complete content: 2 retrieval activities, 1 skip-check, 1 worked example, 1 video placeholder, 2 fix_the_bug activities, 2 choose_tests activities, and 6 segments in the approved order.

## Content Summary

### Activity IDs authored

| ID | Kind | Purpose | Description |
|----|------|---------|-------------|
| 501 | multiple_choice | retrieval | Existing — "when BFS finds a vertex" (kept unchanged) |
| 502 | multiple_choice | retrieval | New — "which graphs BFS fits" (module 3/4 recall; website reachability) |
| 503 | multiple_choice | practice (obj 7) | Skip-check — "spot the visited-too-late bug" |
| 504 | fix_the_bug | practice (obj 7) | Bug A: visited-too-late (line ids 101–113, corrections 120–123) |
| 505 | fix_the_bug | practice (obj 7) | Bug B: appends-unreachable (line ids 151–166, corrections 170–171) |
| 506 | choose_tests | practice (obj 7) | Choose tests for Bug A code |
| 507 | choose_tests | practice (obj 7) | Choose tests for Bug B code |

### Segment IDs authored

| ID | Kind | Notes |
|----|------|-------|
| 501 | worked_example | Debugging visited-too-late step by step; `skip_check_activity_id: 503` |
| 502 | video | Placeholder; body references Wave 2 narration script |
| 503 | activity | → activity 504 (fix_the_bug A) |
| 504 | activity | → activity 505 (fix_the_bug B) |
| 505 | activity | → activity 506 (choose_tests A) |
| 506 | activity | → activity 507 (choose_tests B) |

Segment order: `[502 (video), 501 (worked_example), 503, 504, 505, 506]`

### Bug A: visited-too-late

**Faulty code** (activity 504): `visited = set()` at start; `visited.add(v)` after popleft (before neighbour loop); NO `visited.add(n)` inside the if.

**Faulty lines**: 103 (`visited = set()`), 108 (`visited.add(v)`)

**Corrections used in fixed program**: 120 (`visited = {start}`), 121 (`visited.add(n)`)

**Wrong corrections (distractors)**: 122 (`visited = []`), 123 (`order.append(n)`)

**Fixed program order**: `[101, 102, [120, 104, 105], 106, 107, 109, 110, 111, [121, 112], 113]`

**Test graph**: undirected A–B–C–D–A + A–C, start A. Cycle creates two paths to C and D.

### Bug B: appends-unreachable

**Faulty code** (activity 505): correct BFS body + extra loop `for v in graph.adjacency: if v not in visited: order.append(v)`.

**Faulty lines**: 163–165 (the extra loop)

**No replacement corrections used**: both 170 and 171 are distractors (wrong fixes).

**Fixed program order**: `[151, 152, [153, 154, 155], 156, 157, 158, 159, 160, [161, 162], 166]` — omits 163–165 entirely.

**Feedback on faulty lines**: 163, 164, 165 all explained.

### Choose-tests expected arrays (computed by BFS engine)

All five test cases are shared between activity 506 and 507:

| ID | Graph | Start | Expected |
|----|-------|-------|----------|
| cycle | undirected A–B–C–D–A + A–C | A | [A, B, C, D] |
| two-islands | undirected A–B, B–C, D–E | A | [A, B, C] |
| line | undirected V–W–X–Y–Z | X | [X, W, Y, V, Z] |
| tree | undirected A–B, A–C, B–D | A | [A, B, C, D] |
| one-way | directed A→B, B→C, C→A, D→A | A | [A, B, C] |

### Exposing sets (confirmed by running both buggy versions on each test)

**Activity 506 (Bug A, visited-too-late)**:
- `exposing: ["cycle"]` — Bug A produces `[A, B, C, D, C, D]` on the cycle graph (D and C added twice). No other test exposes it.
- `two-islands`: no cycle, BFS reaches all 3 reachable vertices cleanly → passes.
- `line`, `tree`: no alternate paths while waiting → passes.
- `one-way`: the only cycle returns to A which is already visited → passes.

**Activity 507 (Bug B, appends-unreachable)**:
- `exposing: ["two-islands", "one-way"]` — extra loop adds D, E (two-islands) and D (one-way) to order.
- `cycle`, `line`, `tree`: all vertices reachable from start → extra loop adds nothing → passes.

## Key Decisions

1. **Line IDs**: Used 101–113 for Bug A (not 1–13 as in module 6, 621) and 151–166 for Bug B to keep ids distinct and make it clear these are fresh activities. Correction IDs: 120–123 (Bug A), 170–171 (Bug B).

2. **Bug B fix approach**: The fix is purely removal of lines 163–165. No "replacement" correction is needed — the student leaves those lines out. Two distractors (170, 171) were included as required by the schema (corrections list min_length=1 is not enforced but needed for meaningful wrong-correction presentation).

3. **Worked example graph**: Used the same cycle graph as the choose_tests/fix_the_bug to keep the module coherent — the student sees the same graph in the worked example, the fix_the_bug activity, and the choose_tests activity.

4. **Skip-check activity (503)**: Tests exactly the bug the worked example teaches (visited-too-late on a cycle). A student who answers correctly can skip the worked example.

5. **Retrieval 502**: On BFS fitness (module 3/4 topic) — distinct from 501 which covers when BFS marks vertices. Kept `objective_id` null (as per retrieval rules — `objective_id` is not required for retrieval items, and the existing 501 also has no `objective_id` field).

6. **Segments vs activities namespacing**: Segment IDs and activity IDs are separate tables. Segment 501 and activity 501 coexist without collision.

7. **Three-part feedback**: All feedback messages follow the "Not quite. [reason]. [what to try]." pattern as required by the authoring guide.

8. **Hint levels 1–4**: Every activity has all four levels. Level 4 starts with "Answer:".

## Library Docs Consulted (Context7)

None — this was pure JSON content authoring. No third-party library APIs were called or looked up.

## Build & Test Results

```
seed --check: fixtures valid (7 modules, 118 activities, 7 review paths, 4 graphs); templates valid (choose_tests, fill_in, fix_the_bug, matching, multiple_choice, parsons, trace)
```

Exit status 0. All Pydantic validation passed, all choose_tests expected arrays matched the BFS engine, fix_the_bug order consistency verified, retrieval-not-in-segments rule satisfied.

## Open Issues for Waves 2–3

- **Wave 2 (narration script)**: Write `docs/id/module-5/narration-script.md`. The video segment (502) body references this path. The script should cover: (a) tracing the visited-too-late bug on the cycle graph (same graph as worked example — Vertices: A, B, C, D; Edges: A–B, B–C, C–D, D–A, A–C); (b) showing the fix; (c) brief section on choosing test cases (cycle vs disconnected). Checkpoint questions go at the pauses — suggest one checkpoint asking which graph exposes the visited-too-late bug.

- **Wave 3 (test file)**: Create `api/tests/test_module_5.py` testing: (1) 2 retrievals, none in segments; (2) all activities have 4 hints, level-4 starts with "Answer:"; (3) all wrong options have feedback; (4) worked example has skip_check_activity_id=503 pointing at a valid practice activity; (5) fix_the_bug: faulty program fails BFS, fixed program passes; (6) fix_the_bug: each wrong correction breaks BFS; (7) choose_tests expected arrays match engine; (8) choose_tests exposing sets are exactly the tests the buggy code fails (run buggy code on each test case); (9) test sets include "cycle" and "two-islands" ids in both choose_tests activities.

- **Wave 4**: Run `scripts/check.sh` (full ruff + mypy + pytest + web build). No Python changes were made, so ruff/mypy should pass unchanged. pytest may reveal new issues once test_module_5.py is created.
