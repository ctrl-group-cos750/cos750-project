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

---

## Developer Notes — Wave 2: narration script

### Files Created
- `docs/id/module-5/narration-script.md` — narrated video script for segment 502. Two sections: (1) visited-too-late bug traced on the cycle graph with the fix shown; (2) choosing test cases (cycle exposes Bug A, disconnected graph exposes Bug B). One checkpoint at 1:35. WCAG 1.1.1 text descriptions for both graphs.

### Files Modified
_(none)_

### Key Decisions

1. **Two-section structure**: Section 1 (0:00–1:50) covers the visited-too-late bug; Section 2 (2:00–2:45) covers choosing test cases. Total ≈ 2:45, within the 2:30–3:00 target. The module body (worked example + activities) covers the remaining ~7 minutes of the 10-minute module.

2. **Same cycle graph throughout**: Vertices A, B, C, D; Edges A–B, B–C, C–D, D–A, A–C — identical to activities 504 and 506, so the video reinforces what students will do in the activities without introducing a new graph.

3. **Single checkpoint at 1:35**: Placed just before the reveal of the double-dequeue outcome, forcing students to predict what the faulty BFS does with D while it's still in the queue. Question uses the exact scenario from the trace, matching the module-3/4 pattern of asking students to predict a BFS step. Three options: correct answer + two distractors with targeted feedback (one about checking the queue vs visited, one about queue reordering).

4. **Two-islands graph in Section 2**: Introduced briefly at 2:20 to motivate the choose_tests activities; no checkpoint here because the activities themselves provide that practice. WCAG text description included inline (not in the header) because the graph only appears in Section 2.

5. **ASCII art representation**: Used a square-with-diagonal layout for the cycle graph to show the A–C shortcut clearly. Matches the graph's structure (A top-left, B top-right, C bottom-right, D bottom-left, diagonal A–C).

6. **Sibling format matched exactly**: Title line, reading-pace note, on-screen note, ASCII art + text description, horizontal rule, video section with timestamp table, notes block, horizontal rule, checkpoint section with question/options/(✓)/feedback/hints — all follow modules 1–4.

### Library Docs Consulted (Context7)

None — this was pure Markdown content authoring.

### Build & Test Results

File created and committed. No build step needed for a Markdown file. Seed check (from Wave 1) still passes unchanged — no JSON was modified.

### Open Issues

- **Wave 3**: Create `api/tests/test_module_5.py` per the plan in Wave 1 open issues.
- **Wave 4**: Run `scripts/check.sh` — ruff/mypy/pytest/build.
- **Recording note**: The ASCII art diagonal (╲) may render differently in some editors but is correct Unicode. Whoever records should draw the graph from the description, not the ASCII art.

---

## Developer Notes — Wave 3: module-5 content tests

### Files Created
- `api/tests/test_module_5.py` — 28 tests covering all Wave 3 requirements

### Files Modified
_(none)_

### Key Decisions

1. **Reused helpers from test_module_6.py, not imported**: `GRAPH`, `run_bfs_code`, `_run`, `time_limit`, `passes_hidden`, `first_order`, `lines_text`, `scenario` are all copied verbatim or near-verbatim from test_module_6.py. The existing codebase does not export them from a shared helper module; duplicating them is the established pattern (test_module_6.py itself inlines everything). Importing across test files would require structural changes outside scope.

2. **HIDDEN test set**: Identical to the one in test_module_6.py (nine representative graphs: line, cycle, sports-centre, sports-centre-from-g, residence, residence-from-u, out-of-order, two-islands, one-way). This is the natural hidden-test set for "passes_hidden" and has proven power to catch both Bug A (visited-too-late) and Bug B (appends-unreachable).

3. **test_every_wrong_answer_has_feedback**: Covers all three activity kinds present in module 5 (multiple_choice, fix_the_bug, choose_tests). Each asserts `fb[key]` is truthy — the three-part feedback pattern is checked by presence (non-empty string), matching how test_module_2.py and test_module_6.py assert feedback presence.

4. **test_non_retrieval_activities_cover_objective_7**: Asserts `{a.objective_id for a in non_retrieval} == {7}`. Retrieval activities have `objective_id=None`, so they are correctly excluded.

5. **Both choose_tests exposing sets verified in two separate tests**: One test checks engine correctness (expected arrays), another checks the exposing-set derivation by actually running the faulty code. This matches the test_module_6 pattern exactly.

### Library Docs Consulted (Context7)

None — no third-party library APIs were used beyond those already established by test_module_2.py and test_module_6.py.

### Build & Test Results

```
# test_module_5.py alone
.venv/bin/pytest -q tests/test_module_5.py
28 passed in 1.01s

# ruff format check
ruff format --check tests/test_module_5.py
1 file already formatted

# ruff lint
ruff check tests/test_module_5.py
All checks passed!

# mypy --strict
mypy tests/test_module_5.py
Success: no issues found in 1 source file

# full suite
.venv/bin/pytest -q
7 failed, 2056 passed, 23 skipped in 123.14s
```

### Pre-existing Failures (Wave 1 content bugs — NOT introduced by this wave)

All 7 failures were confirmed present before test_module_5.py was added (verified by git stash):

| Test | Activity | Root cause |
|---|---|---|
| `test_choose_tests_text_never_names_a_test_by_its_stored_id` | 507 | Level-4 hint says "two-islands and one-way" — these are stored test case IDs |
| `test_plain_text_fields_carry_no_markdown[504]` | 504 | `config.prompt` contains `\n` line breaks (not allowed in plain-text fields) |
| `test_plain_text_fields_carry_no_markdown[505]` | 505 | Same issue |
| `test_every_module_with_content_opens_by_gaining_attention` | — | Module 5 not in `HOOKS` dict in test_content_cues.py (module needs a text or worked_example first, but the test checks for a hook segment id); test expects module 5 to declare a hook id |
| `test_no_two_choose_tests_items_have_the_same_answer` | 507 | Activity 507 has the same exposing set (`{two-islands, one-way}`) as activity 624 in module 6 |
| `test_the_first_correction_listed_is_never_a_right_one[504]` | 504 | The first correction in `config.corrections` (id 120) is one of the correct corrections used in `solution.order` |
| `test_every_video_segment_has_its_narration_as_text` | — | Video segment 502 body references narration script path but does not embed it as text (Wave 2 content issue) |

These failures require Wave 1 content fixes. They are out of scope for Wave 3 (tests only).

### Open Issues
- The 7 pre-existing failures above need to be fixed in the Wave 1 content (module-5.json) before the full check.sh gate will pass. Key fixes needed: (1) rename stored test IDs so they don't look like display text in hints; (2) remove `\n` from `config.prompt` fields in activities 504 and 505; (3) add module 5 to the `HOOKS` dict in test_content_cues.py or add a text/hook opening segment; (4) make activity 507's exposing set distinct from 624's (different test case IDs); (5) reorder corrections in 504 so the first listed is a wrong one; (6) fix video segment 502 body so it embeds the narration text.

---

## Developer Notes — Wave 4: fix 7 content-convention violations

### Files Modified
- `api/app/seed/module-5.json` — fixed all 6 content violations (see below)
- `api/tests/test_content_cues.py` — added module 5 to HOOKS dict; updated no-segments guard

### Fixes Applied

#### Fix 1 — Rule: test_choose_tests_text_never_names_a_test_by_its_stored_id (activity 507)
**Problem**: Level-4 hint said "Answer: two-islands and one-way" — those are stored test case ids with hyphens.
**Fix**: Rewrote hint to refer by test number: "Answer: Test 2. In that graph, at least one vertex cannot be reached from the start, so the extra loop adds it wrongly. The faulty version passes the other tests." (After fix 5 replaced "one-way" with "directed-tree", only Test 2 is in the exposing set.)

#### Fix 2 — Rule: test_plain_text_fields_carry_no_markdown (activity 504)
**Problem**: `config.prompt` contained `\n` line breaks between three paragraphs.
**Fix**: Merged into one plain-text paragraph describing the graph inline: "The graph has vertices A, B, C, D and undirected edges A-B, B-C, C-D, D-A and A-C, starting at A."

#### Fix 3 — Rule: test_plain_text_fields_carry_no_markdown (activity 505)
**Problem**: Same — `config.prompt` contained `\n` line breaks.
**Fix**: Merged into one plain-text paragraph: "The graph has two islands: vertices A, B, C, D, E with undirected edges A-B, B-C and D-E, starting at A."

#### Fix 4 — Rule: test_every_module_with_content_opens_by_gaining_attention
**Problem**: Module 5 now has segments but was not in the HOOKS dict, so the test had no expected hook segment id for it.
**Fix**: Added `5: 501` to `HOOKS` in `api/tests/test_content_cues.py`. Segment 501 (worked_example) is module 5's first text/worked_example; the segment immediately after it (503) is `kind="activity"`, satisfying `after.kind == "activity"`. Also updated the comment (removed "Module 5 has no segments yet") and changed the no-segments guard from `assert m.id == 5` to `assert m.id not in HOOKS` so it works correctly for any future module that starts empty.

#### Fix 5 — Rule: test_no_two_choose_tests_items_have_the_same_answer (activity 507)
**Problem**: Activity 507's exposing set `{"two-islands", "one-way"}` was identical to activity 624's (module 6).
**Fix**: Replaced the "one-way" test case (directed A→B, B→C, C→A, D→A, start A — D unreachable) with "directed-tree" (directed A→B, A→C, B→D, start A — all vertices reachable). The appends-unreachable code passes "directed-tree" (BFS reaches all 4 vertices). Exposing set becomes `{"two-islands"}` ≠ 624's `{"two-islands", "one-way"}`. BFS engine output for directed-tree confirmed as `["A", "B", "C", "D"]`. AC2 still satisfied: test set includes "cycle" and "two-islands", and the disconnected "two-islands" graph exposes the Bug B bug.

#### Fix 6 — Rule: test_the_first_correction_listed_is_never_a_right_one (activity 504)
**Problem**: First correction in `config.corrections` was id 120 (`visited = {start}`), which appears in `solution.order`.
**Fix**: Reordered corrections list to `[122, 120, 121, 123]` — distractor 122 (`visited = []`) is now first. The `solution.order` is unchanged; only the display order of the corrections list changed.

#### Fix 7 — Rule: test_every_video_segment_has_its_narration_as_text (segment 502)
**Problem**: Segment 502 body was a placeholder: "Staff attach the narrated video to this segment..."
**Fix**: Replaced with the full narration text extracted from `docs/id/module-5/narration-script.md` — all spoken narration from both sections, in prose (no stage directions, no `[slide]`, no "on screen", no "CHECKPOINT" markers). Word count: ~477 words (well above the 150-word minimum). Also removed the word "unvisited" (which violates the found/visited vocabulary rule in `test_found_and_visited_mean_what_module_3_says`) — replaced with "every vertex BFS never reached".

### Key Decisions

1. **Fix 5 approach**: Replaced "one-way" with "directed-tree" rather than changing the "two-islands" graph, because test_module_5.py's `test_both_choose_tests_activities_include_cycle_and_two_islands` requires the id "two-islands" to remain in activity 507. Using a fully-reachable directed graph gives exposing = `{"two-islands"}` which is minimal and correct.

2. **Vocabulary check on video body**: After embedding the narration, discovered that the word "unvisited" appeared in the body ("appends every unvisited vertex"). The `test_found_and_visited_mean_what_module_3_says` test bans "unvisited" because it implies a vertex waiting in the queue is "unvisited" when the module-3 definition says it is "found". Replaced with "every vertex BFS never reached" — semantically equivalent and vocabulary-compliant.

3. **HOOKS guard update**: Changed `assert m.id == 5` to `assert m.id not in HOOKS` so the test is future-proof — if a new module starts empty it won't falsely claim to be module 5.

### Library Docs Consulted (Context7)

None — pure JSON content and test file editing.

### Build & Test Results

```
seed --check: fixtures valid (7 modules, 118 activities, 7 review paths, 4 graphs); templates valid
(choose_tests, fill_in, fix_the_bug, matching, multiple_choice, parsons, trace)

pytest -q (full suite):
2063 passed, 23 skipped in 120.99s
(23 skips are all pre-existing Postgres-only tests: row locks, migrations, support)

ruff format --check tests/test_content_cues.py: 1 file already formatted
ruff check tests/test_content_cues.py: All checks passed!
mypy tests/test_content_cues.py: Success: no issues found in 1 source file
```

The 7 previously-failing tests now pass:
- test_choose_tests_text_never_names_a_test_by_its_stored_id ✓
- test_plain_text_fields_carry_no_markdown[504] ✓
- test_plain_text_fields_carry_no_markdown[505] ✓
- test_every_module_with_content_opens_by_gaining_attention ✓
- test_no_two_choose_tests_items_have_the_same_answer ✓
- test_the_first_correction_listed_is_never_a_right_one[504] ✓
- test_every_video_segment_has_its_narration_as_text ✓

No new failures introduced (the "unvisited" vocabulary issue was caught and fixed before final commit).

### Open Issues

None. Branch: feat/module-5-test-and-debug. Not pushed.

---

## Developer Notes — Wave 4 (CI gate): full scripts/check.sh verification

### Files Created
_(none)_

### Files Modified
_(none — the check required only a local `npm ci` to restore node_modules; no tracked files changed)_

### Environment Setup
- Node version: `v24.22.2` (from `web/.nvmrc`), loaded via `~/.nvm/versions/node/v24.22.2/bin`.
- `api/.venv` already present with all deps.
- `web/node_modules` existed but `mdast-util-gfm-table` and `micromark-extension-gfm-table` were absent — pre-existing local environment issue (both packages are in `package.json` and `origin/staging`). Fixed with `npm ci` (no tracked file change).

### Pre-existing web test failure (proved, not introduced by this branch)
Before `npm ci`, 22 Vitest suites failed with:
```
Error: Failed to resolve import "mdast-util-gfm-table" from "src/components/Markdown.tsx"
Error: Failed to resolve import "micromark-extension-gfm-table" from "src/components/Markdown.tsx"
```
Both packages were already listed in `web/package.json` on `origin/staging` (confirmed via `git show origin/staging:web/package.json`). The failure was a stale local `node_modules`, not a branch regression. `npm ci` resolved it.

### scripts/check.sh result (full run, Node 24.22.2)

```
== web
  format:check  ✓  All matched files use Prettier code style!
  lint          ✓  Found 0 warnings and 0 errors (oxlint, 166 files, 219 rules)
  test          ✓  37 passed (455 tests) — vitest run
  build         ✓  tsc -b + vite build succeeded (2702 modules transformed)
  check:api     ✓  openapi-typescript regenerated schema.d.ts; git diff --exit-code clean

== api
  ruff format   ✓  143 files already formatted
  ruff check    ✓  All checks passed!
  mypy          ✓  Success: no issues found in 124 source files
  pytest (full) ✓  2063 passed, 23 skipped in ~129 s
  pytest (cov)  ✓  252 passed, 1 skipped; coverage 99.14% ≥ 90% gate

== all checks passed
```

### seed --check result
```
seed --check: fixtures valid (7 modules, 118 activities, 7 review paths, 4 graphs);
templates valid (choose_tests, fill_in, fix_the_bug, matching, multiple_choice, parsons, trace)
```
Exit status 0.

### Key Decisions
No code changes were needed. The only action was `npm ci` to restore the local `node_modules` to the state described by `package-lock.json`. This is an environment fix, not a branch fix.

### Library Docs Consulted (Context7)
None.

### Build & Test Results
Full CI gate green. Branch: `feat/module-5-test-and-debug`. Not pushed.

### Open Issues
None. Branch is ready for PR review.

---

## Developer Notes — Wave 5: reviewer Critical + Important fixes

### Files Modified
- `api/app/seed/module-5.json` — diamond graph substitution (CRITICAL 1) in four locations
- `docs/id/module-5/narration-script.md` — diamond graph substitution + vocabulary fix (CRITICAL 1 + 2) + contraction fix (nitpick)
- `api/tests/test_module_5.py` — pure-deletion branch in `test_each_wrong_correction_leaves_bfs_broken` (IMPORTANT)

### Fixes Applied

#### CRITICAL 1 — Diamond graph substitution (5 locations in 2 files)

**Root cause**: The worked-example trace text, video body prose, and narration script were all written for the diamond graph (adj[A]=[B,C], adj[B]=[A,D], adj[C]=[A,D], adj[D]=[B,C]). But the fixture used a 5-edge cycle (A-B, B-C, C-D, D-A, A-C) whose Bug A output is [A,B,C,D,C,D] (both C and D revisited), not [A,B,C,D,D] as stated.

**Verified on diamond before touching any file:**
- Correct BFS from A: `[A, B, C, D]` ✓
- Bug A (visited-too-late) output: `[A, B, C, D, D]` ✓ — D is the only revisit (C sees D in queue but D is not yet in visited, enqueues it again)
- Bug B output: `[A, B, C, D]` (all vertices reachable, extra loop adds nothing) ✓
- 506 exposing set unchanged: `["cycle"]` (diamond fails, all others pass) ✓
- 507 exposing set unchanged: `["two-islands"]` (diamond passes, two-islands fails) ✓

**Changes made:**

1. `segment 501` (worked_example body): "The graph we use" paragraph changed from "Edges: A–B, B–C, C–D, D–A, A–C … cycle A–B–C–D–A and shortcut A–C" to "Edges: A–B, A–C, B–D, C–D … diamond shape: A is at the top and connects to both B and C; B and C both connect to D at the bottom." Trace table D-dequeue row fixed from "D leaves; adds A (already visited)" to "D leaves; B and C are visited, nothing new added" (diamond: adj[D]=[B,C], not [A]).

2. `segment 502` (video body): ASCII art replaced (5-edge box-with-diagonal → simple rectangle A-B/A-C/B-D/C-D); text description rewritten to "4 edges: A–B, A–C, B–D, C–D … diamond shape … cycle A–B–D–C–A"; trace narration step for C updated to "C leaves. A is found. But D?" (removed "and B" since adj[C]=[A,D] not [A,B]).

3. `activity 504` (fix_the_bug prompt): "edges A-B, B-C, C-D, D-A and A-C" → "edges A-B, A-C, B-D, C-D (a diamond: A connects to B and C, which both connect to D)".

4. `activity 506` (choose_tests "cycle" TestCase): 5 edges → 4 edges (A-B, A-C, B-D, C-D); expected unchanged ([A,B,C,D] — same output on diamond). Feedback for "cycle" updated to "two paths reach D before it leaves the queue" (removes incorrect "and a shortcut" and "both C and D").

5. `activity 507` (choose_tests "cycle" TestCase): same edge swap as 506 above.

6. `narration-script.md` header: "same cycle graph" → "same diamond graph"; ASCII art updated (5-edge → 4-edge rectangle); text description updated; notes-for-recorder updated (cycle graph + A–B, B–C, C–D, D–A, A–C → diamond graph + A–B, A–C, B–D, C–D); checkpoint question updated ("cycle graph A–B–C–D–A with shortcut A–C" → "diamond graph A–B, A–C, B–D, C–D").

#### CRITICAL 2 — Banned word "unvisited" in narration script

`narration-script.md` timestamp 2:20 row: "every **unvisited** vertex at the end" → "every vertex BFS never reached". This matches the phrasing already used in segment 502's video body and satisfies `test_found_and_visited_mean_what_module_3_says`. Also fixed contraction "can't" → "cannot" at timestamp 2:35 (house style matches sibling scripts).

#### IMPORTANT — `test_each_wrong_correction_leaves_bfs_broken[505]` trivially passing

**Root cause**: activity 505's fix is pure deletion — `solution.order` contains no correction IDs, so `used = []`. The existing `for wrong in unused: for right in used:` loop never executes.

**Fix**: Added a `if not used:` branch before the existing loop. When the fix is pure deletion, the branch iterates each distractor, builds `appended = [*first_order(a), wrong["id"]]`, and asserts `not passes_hidden(lines_text(a, appended))`.

**Verified before adding the test**: distractor 170 (`for v in sorted(graph.adjacency):`) raises `IndentationError` when appended as a standalone for-loop with no body; distractor 171 (`if v not in order:`) raises `IndentationError` for the same reason. Both cause `passes_hidden` to return `False` → assertion holds. ✓

**Ruff lint**: initial code used list concatenation `first_order(a) + [wrong["id"]]`; ruff RUF005 required spread syntax `[*first_order(a), wrong["id"]]`. Fixed.

### Key Decisions

1. **Why Option A (diamond) over Option B (rewrite trace)**: The trace text was already correct for the diamond — only the fixture graph was wrong. Switching the fixture is a one-line change per location; rewriting the trace would require changing 6 prose sentences plus the table.

2. **HIDDEN suite unchanged**: `HIDDEN["cycle"]` in `test_module_5.py` still uses the 5-edge cycle (A-B, B-C, C-D, D-A, A-C). This is correct — HIDDEN is the hidden test suite used to judge whether arbitrary BFS code "passes", not the choose_tests fixture cases. Bug A still fails HIDDEN["cycle"] and HIDDEN["sports-centre"] etc. on the 5-edge graph.

3. **Segment 502 ASCII art**: Changed from a box-with-diagonal to a plain rectangle because the diamond graph has no diagonal. The four vertices A (top-left), B (top-right), C (bottom-left), D (bottom-right) with edges A-B (top), A-C (left), B-D (right), C-D (bottom) forms a plain rectangle — which is the correct visual for A-B, A-C, B-D, C-D.

4. **506 feedback for "cycle"**: Updated to "two paths reach D before it leaves the queue" (not C and D as in 5-edge). On the diamond, only D is reached by two paths (via B and via C). C is reached only by A directly.

### Recomputed expected arrays for changed TestCases

| Activity | Test ID | Old edges | New edges | Expected (unchanged) |
|----------|---------|-----------|-----------|----------------------|
| 506 | cycle | A-B,B-C,C-D,D-A,A-C | A-B,A-C,B-D,C-D | [A,B,C,D] |
| 507 | cycle | A-B,B-C,C-D,D-A,A-C | A-B,A-C,B-D,C-D | [A,B,C,D] |

Expected `[A,B,C,D]` is correct on the diamond: BFS from A visits A→B,C→D (D found by both B and C, but only enqueued once by the correct engine). Confirmed by running `run_bfs(diamond)`.

### Library Docs Consulted (Context7)

None — pure JSON content, Markdown, and Python test authoring.

### Build & Test Results

```
seed --check: fixtures valid (7 modules, 118 activities, 7 review paths, 4 graphs);
templates valid (choose_tests, fill_in, fix_the_bug, matching, multiple_choice, parsons, trace)

pytest -q (module-5 only): 28 passed in 0.93s
pytest -q (full suite): 2063 passed, 23 skipped in ~115s
ruff format --check tests/test_module_5.py: 1 file already formatted
ruff check tests/test_module_5.py: All checks passed!
mypy tests/test_module_5.py: Success: no issues found in 1 source file
scripts/check.sh (full, Node 24.22.2):
  web: format ✓, lint ✓, tests (455 passed, 37 suites) ✓, build ✓, check:api ✓
  api: ruff format ✓, ruff check ✓, mypy ✓,
       pytest 2063 passed 23 skipped ✓, coverage 99.14% ≥ 90% ✓
== all checks passed (exit 0)
```

### Open Issues

None. All CRITICAL and IMPORTANT reviewer findings resolved. Branch: `feat/module-5-test-and-debug`. Not pushed.

---

## Developer Notes — Wave 6: residual 'A and B' wording fix

### Files Modified
- `api/app/seed/module-5.json` — trace table row 3 in segment 501 worked_example body
- `docs/id/module-5/narration-script.md` — 1:20 row on-screen note and narration text

### Exact Before / After

**Edit 1 — module-5.json, segment 501 trace table (row for C-dequeues):**

Before:
```
| [C, D] | C leaves; A and B are visited, but D is not in visited yet (it joined at step 2 but visited.add(D) hasn't run), so **D joins again** | {A, B, C} |
```

After:
```
| [C, D] | C leaves; A is visited, but D is not in visited yet (it joined at step 2 but visited.add(D) hasn't run), so **D joins again** | {A, B, C} |
```

**Edit 2 — docs/id/module-5/narration-script.md, 1:20 row:**

Before:
```
| 1:20 | C dequeues; A and B (visited), D highlighted with warning arrow | C leaves. A and B are found. But D? … |
```

After:
```
| 1:20 | C dequeues; A (visited), D highlighted with warning arrow | C leaves. A is found. But D? … |
```

### Rationale
On the diamond graph (adj[C] = [A, D]), when C dequeues it only examines
its two neighbours A and D. B is visited by then but is never a neighbour
of C and is never examined by C. Saying "A and B are visited" implies C
checks B, which gives students a wrong mental model of the adjacency
structure.  The fix matches the already-correct segment 502 video body
("C leaves. A is found. But D?").

### Library Docs Consulted (Context7)
None — wording-only content edit.

### Build & Test Results

```
seed --check: fixtures valid (7 modules, 118 activities, 7 review paths, 4 graphs)
Exit status: 0

scripts/check.sh (Node 24.22.2, full run):
  web: format ✓, lint ✓, tests 455 passed (37 suites) ✓, build ✓, check:api ✓
  api: ruff format ✓, ruff check ✓, mypy ✓,
       pytest 2063 passed, 23 skipped ✓, coverage 99.14% ≥ 90% ✓
== all checks passed (exit 0)
```

### Open Issues
None. Branch: feat/module-5-test-and-debug. Not pushed.

---

## Local Run Note — module 5 (Test and debug)

**Date:** 2026-11-12  
**Branch:** `feat/module-5-test-and-debug`

### Stack Status

| Component | Status | URL / Details |
|---|---|---|
| Postgres (Docker) | ✅ running | localhost:5432, schema `0017` |
| API (uvicorn --reload) | ✅ running | http://localhost:8000 — `{"status":"ok","database":"ok","schema":"0017"}` |
| Frontend (Vite dev) | ✅ running | http://localhost:5173 (proxies `/api` → :8000) |

Migrations were applied (`alembic upgrade head` — ran migrations 0015, 0016, 0017).  
Seed ran with `DEMO_PASSWORD=Demo1234!`: 7 modules, 118 activities, 4 demo accounts created.

### Demo accounts (seeded, password: `Demo1234!`)

| Email | Stage |
|---|---|
| `new@demo.example.com` | Brand new — nothing done |
| `mid@demo.example.com` | Partway through module 3 |
| `not-yet@demo.example.com` | Finished all modules, objective 6 "not yet" |
| `ready@demo.example.com` | Finished, ready for lecture |

⚠️ The `not-yet` and `ready` accounts have **already completed** module 5, so they can revisit it but will see it pre-answered. **Best path for fresh testing: register a new account + run the unlock snippet below.**

### Module 5 content map

| Step | What | Detail |
|---|---|---|
| Before segments | 2 × retrieval | activity 501 & 502 (multiple_choice) — must answer both to proceed |
| Seg pos=1 | Video: "Debugging a faulty BFS" | No checkpoints in DB; auto-done |
| Seg pos=2 | Worked example | Embeds activity 503 (multiple_choice "Check: spotting a BFS bug") with skip-check |
| Seg pos=3 | fix_the_bug #1 | "Fix the bug: the visited-too-late BFS" (activity 504) — 4 hints |
| Seg pos=4 | fix_the_bug #2 | "Fix the bug: the appends-unreachable BFS" (activity 505) — 4 hints |
| Seg pos=5 | choose_tests #1 | "Choose the tests: visited-too-late bug" (activity 506) — 4 hints |
| Seg pos=6 | choose_tests #2 | "Choose the tests: appends-unreachable bug" (activity 507) — 4 hints |

### Unlock snippet (LOCAL ONLY — run after registering)

After registering a new account in the app, run this from `api/` to mark modules 0–4 complete so module 5 unlocks immediately:

```bash
cd /Users/ayandajuqu/UP_Hons/cos750/cos750-project/api

DATABASE_URL="postgresql+psycopg://ctrl:b04e346b1c4f4168b814dd5be1204fd6def2a2177ce0d701@localhost:5432/ctrl" \
.venv/bin/python -c "
import os, datetime
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.models import ModuleProgress, Module, Segment, User

EMAIL = 'YOUR_EMAIL_HERE'   # <-- replace with your registered email

engine = create_engine(os.environ['DATABASE_URL'])
with Session(engine) as s:
    user = s.scalar(select(User).where(User.email == EMAIL))
    if user is None:
        print(f'No user found with email {EMAIL}'); exit(1)
    for mod in s.scalars(select(Module).where(Module.id.in_([0,1,2,3,4])).order_by(Module.id)):
        segs = s.scalars(select(Segment).where(Segment.module_id == mod.id).order_by(Segment.position)).all()
        last_pos = segs[-1].position if segs else 0
        prog = s.scalar(select(ModuleProgress).where(ModuleProgress.user_id == user.id, ModuleProgress.module_id == mod.id))
        if prog is None:
            prog = ModuleProgress(user_id=user.id, module_id=mod.id, status='complete',
                                  current_segment_position=last_pos,
                                  completed_at=datetime.datetime.now(datetime.UTC))
            s.add(prog)
        else:
            prog.status = 'complete'; prog.current_segment_position = last_pos
            prog.completed_at = datetime.datetime.now(datetime.UTC)
        print(f'  Module {mod.id} ({mod.title}): marked complete')
    s.commit()
    print('Done — refresh the app; module 5 is now unlocked.')
"
```

Tested: snippet verified to unlock module 5 (sets status `open`) without errors on a throwaway account; throwaway user was deleted after testing.

### How to stop everything

```bash
pkill -f "uvicorn app.main:app"
pkill -f "vite"
cd /Users/ayandajuqu/UP_Hons/cos750/cos750-project
docker compose -f docker-compose.yml -f docker-compose.local.yml stop db
```

Logs: API and frontend log to their respective terminal sessions. Check with:
```bash
# API process logs (if started in background terminal)
ps aux | grep uvicorn
ps aux | grep vite
```

---

## Developer Notes — Vite import error fix (stale node_modules)

### Files Created
_(none)_

### Files Modified
_(none — environment fix only; no tracked files changed)_

### Diagnosis

Both `mdast-util-gfm-table` and `micromark-extension-gfm-table` were confirmed present in `web/package.json` and `web/package-lock.json` (versions 2.0.1 and 2.1.2). However the running Vite process (PID 32559, correctly using Node v24.22.2) was returning `Failed to resolve import` errors because the `vite:import-analysis` plugin could not find these packages during its module-resolution pass. The packages appeared to exist as directories in `node_modules/` but the dep-optimization cache (`node_modules/.vite/deps/`) had no entries for them, indicating `node_modules` had been populated partially — likely from a `git merge` of staging work without a subsequent `npm ci`.

Root cause: stale `node_modules` from a merged staging commit that added these two packages to `package.json` and `package-lock.json` but was never followed by `npm ci` locally.

### Fix

1. Killed the running Vite server: `kill -9 32559`.
2. Ran `npm ci` with Node 24 explicitly on PATH (the shell defaulted to Node v8.17.0, which cannot run npm 11):
   ```
   PATH="/Users/ayandajuqu/.nvm/versions/node/v24.22.2/bin:$PATH" npm ci
   ```
   Result: `added 310 packages, and audited 317 packages in 3s`, 0 vulnerabilities. No `package.json` change.
3. Restarted Vite in background:
   ```
   PATH="/Users/ayandajuqu/.nvm/versions/node/v24.22.2/bin:$PATH" npm run dev > /tmp/vite.log 2>&1 &
   ```

### Results

- `node_modules/mdast-util-gfm-table` ✅ present  
- `node_modules/micromark-extension-gfm-table` ✅ present  
- Vite started in 1226 ms with no errors in `/tmp/vite.log`  
- `curl http://localhost:5173` → HTTP 200  
- `curl http://localhost:5173/src/components/Markdown.tsx` → correctly resolves both imports via `/node_modules/.vite/deps/mdast-util-gfm-table.js` and `/node_modules/.vite/deps/micromark-extension-gfm-table.js` — no error overlay  
- `git status` shows only pre-existing changes to `.gitignore` and `dev-notes.md` — no tracked-file modifications  

### Library Docs Consulted (Context7)
None — environment fix, no library API changes.

### Build & Test Results
Frontend dev server running at http://localhost:5173. Import error resolved. API (:8000) and Postgres left untouched.

### Open Issues
None. Branch: `feat/module-5-test-and-debug`. Not pushed.

## Developer Notes — Service restart (2026-11-12)

### What was down
- **Vite** (`:5173`): dead — ERR_CONNECTION_REFUSED
- **uvicorn / FastAPI** (`:8000`): dead — no response
- **Postgres** (`:5432`): already up and healthy (container `cos750-project-db-1`, up 3 days)

### What was done
No source changes. LOCAL ONLY. Branch confirmed: `feat/module-5-test-and-debug`.

1. Started FastAPI (uvicorn) from `api/` using `.venv/bin/uvicorn app.main:app --reload` with env vars sourced from `.env` (`DATABASE_URL` constructed from `POSTGRES_USER/PASSWORD/DB`, `SECRET_KEY`, `DEMO_PASSWORD=Demo1234!`, `MEDIA_DIR=./media`, `SERVE_MEDIA=1`). Logs at `/tmp/uvicorn.log`.
2. Started Vite from `web/` with `PATH` prefixed to Node v24.22.2 (`$HOME/.nvm/versions/node/v24.22.2/bin`). `node_modules` was intact (no `npm ci` needed). Logs at `/tmp/vite.log`.

### Final status
| Service | Status |
|---|---|
| Postgres (`:5432`) | ✅ up (healthy, Docker) |
| FastAPI (`:8000`) | ✅ `{"status":"ok","database":"ok","schema":"0017"}` |
| Vite (`:5173`) | ✅ HTTP 200 |
| `/modules/5` | ✅ HTTP 200 (SPA index.html) |

### Log paths
- API: `/tmp/uvicorn.log`
- Vite: `/tmp/vite.log`

### To reach module 5
Navigate to `http://localhost:5173/modules/5` — log in first with `ready@demo.example.com` / `Demo1234!` (or any registered account with module 5 unlocked).

## Developer Notes — Branch push and PR (2026-11-12)

### Branch push
- Branch `feat/module-5-test-and-debug` pushed to `origin` via HTTPS keychain token.
- Tracking set: `git push -u origin feat/module-5-test-and-debug`.

### Staging integration check
- `git merge-base HEAD origin/staging` == `origin/staging` HEAD (`c190740`) — branch was already based on the latest staging commit.
- No merge was needed; no conflicts; no new alembic heads (`alembic heads` → `0017 (head)`, single).

### Final checks before PR
- `cd api && .venv/bin/python -m app.seed --check` → **valid** (7 modules, 118 activities, 7 review paths, 4 graphs)
- `scripts/check.sh` → **all checks passed** (2063 pytest + 252 coverage-subset passed, 23 skipped; web 455 tests; coverage 99.14%)

### PR
- **URL**: https://github.com/ctrl-group-cos750/cos750-project/pull/189
- **Title**: `content: module 5 Test and debug (objective 7)`
- **Base**: `staging` ✅
- **Head**: `feat/module-5-test-and-debug`
- **State**: OPEN — awaiting teammate review per DoD (not merged)

### Open Issues
None. PR is open and ready for review.
