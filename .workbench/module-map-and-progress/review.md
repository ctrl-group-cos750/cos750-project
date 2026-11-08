# Review — module-map-and-progress

## Simplification Summary

Pass 1 was already completed by the simplifier before this review. The changes it made were:

- Extracted duplicate `_is_prev_complete_for_user` helper in `services/modules.py` (the 10-line block that appeared identically in `get_module_detail` and `save_position`).
- Removed the redundant `isInteractive` intermediate variable in `ModuleMap.tsx`.
- Simplified the `(isLast && mutation.isPending) || mutation.isPending` condition to `mutation.isPending` in `ModulePage.tsx`.
- Removed the redundant `kind` variable in `SegmentView.tsx` and the now-unused `SegmentKind` type import.

All changes were purely structural; no behaviour was altered. `scripts/check.sh` exits 0.

---

## Issues

### [IMPORTANT] `PositionIn.segment_position` has no non-negative constraint

**File**: `api/app/schemas/modules.py:84`

`segment_position: int` has no lower-bound validator. A malicious or buggy client can POST `{"segmentPosition": -1}`. The service's completion logic (`segment_position >= last_index`, where `last_index >= 0`) correctly avoids marking the module complete, but it then writes `-1` into `module_progress.current_segment_position`, which is semantically invalid. A returning student whose progress row contains `-1` would have `Math.min(-1, segments.length - 1)` clamped to `-1` as `currentIndex`, causing the frontend to access `segments[-1]` which is `undefined` in JavaScript — crashing the ModulePage render.

**Fix**: Add `ge=0` to the field:
```python
from pydantic import Field

class PositionIn(ApiModel):
    segment_position: int = Field(ge=0)
```

---

### [IMPORTANT] Misleading comment in `ModulePage.tsx` (`navigateTo`)

**File**: `web/src/features/module/ModulePage.tsx:52`

The inline comment reads:
```tsx
// Save position (1-based position matches the segment's `position` field).
```
This is wrong. `segment.position` is **0-based** (segments at positions 0, 1, 2 …) — both the fixture validation (`positions == list(range(len(positions)))`) and the migration column definition confirm this. The comment causes the next developer to doubt whether a bug has been introduced every time they look at the save path.

**Fix**: Replace the comment with:
```tsx
// segment.position is 0-based and equals clamped when segments are sequential,
// so sending it directly satisfies the backend contract.
```

---

### [IMPORTANT] `SE §8` deviation: `ModuleProgress` uses `current_segment_position` (int) instead of `current_segment_id` (FK)

**File**: `api/app/models/module.py:68`, `api/app/schemas/modules.py:40`

The SE document §8 specifies:
> **ModuleProgress**: `user_id`, `module_id`, `status`, **`current_segment_id`**, `completed_at`.

The implementation uses `current_segment_position: int` (a 0-based index) instead of a FK to `segments.id`. This was an approved decision (questions.md decision 5 partially addresses surrogate vs composite key, not this specific deviation). However, this is a genuine semantic difference: `current_segment_id` would be robust to segment reordering; `current_segment_position` is not. If Sprint 2 inserts a new segment before the student's saved position, the student resumes at the wrong segment silently.

This is noted in the dev-notes as a conscious trade-off vs the SE document. Because this choice has been approved through the workbench decision process and a workaround (sequential positions enforced by the seed validator) is in place, this is flagged as Important rather than Critical. However, the SE document reference in the schema should be updated to document the deviation.

**Fix** (minimal): Add a comment to `ModuleProgress.current_segment_position` and to `ModuleOut.current_segment_position` explicitly noting the deviation and its implication:
```python
# NOTE: SE §8 specifies current_segment_id (FK). Using a 0-based int position instead
# (approved decision, questions.md). Segment content reordering would require a migration
# to convert back to ids. Seed enforces sequential 0-based positions.
current_segment_position: Mapped[int] = mapped_column(default=0, server_default="0")
```

---

### [IMPORTANT] Refresher-segment filtering is not implemented

**File**: `api/app/services/modules.py` (around line 213–218)

SE §9 specifies:
> `GET /api/modules/{moduleId}` — … Refreshers the diagnostic ruled out are **left out**.

The current `get_module_detail` returns **all** segments including `kind='refresher'`. The FR-8.1 diagnostic that decides which refreshers to show is out of scope for this story (no diagnostic module exists yet), but the API contract already promises to filter. This means the endpoint does not match the SE §9 spec.

In practice this has no student-visible impact today (no refresher segments are seeded and the diagnostic has not been built), but it is a spec non-conformance.

**Fix**: Either add a TODO comment at the query site noting the future gating requirement, or add a query-time filter that excludes `kind='refresher'` segments for now with a TODO to replace it with diagnostic-aware filtering:
```python
# TODO (FR-8.1): filter out refresher segments where the diagnostic has ruled them out.
# For now all non-refresher segments are returned; refreshers are included until the
# diagnostic is built.
segments = session.scalars(
    select(Segment)
    .where(Segment.module_id == module_id)
    .order_by(Segment.position)
).all()
```
(Or filter them entirely now, since there are none in the seed and the test data uses only `text`/`worked_example`.)

---

### [MINOR] `%` placeholder icon for `in_progress` status in `ModuleMap.tsx`

**File**: `web/src/features/module/ModuleMap.tsx:17`

```tsx
case 'in_progress':
  return { tone: 'warning', label: 'in progress', icon: '%' }
```

The `%` character is not a meaningful icon. The other statuses use either an emoji (`🔒`), a geometric character (`○`), or a check mark (`✓`). `%` was likely a placeholder that was never replaced. The Tag component renders the icon with `aria-hidden="true"`, so it does not harm accessibility, but it looks wrong visually.

**Fix**: Replace `'%'` with a more meaningful character such as `'◑'` (half-filled circle, common for "in progress") or `'…'` (ellipsis):
```tsx
case 'in_progress':
  return { tone: 'warning', label: 'in progress', icon: '◑' }
```

---

### [MINOR] Inconsistent progress-bar semantics between `ModuleMap` and `ModulePage`

**File**: `web/src/features/module/ModuleMap.tsx:44` vs `web/src/features/module/ModulePage.tsx:90`

`ModuleMap` renders `value={module.currentSegmentPosition}` (0-based), so a student on segment position 2 of 4 sees `"2 of 4"` in the `showCount` label.

`ModulePage` renders `value={currentIndex + 1}` (1-based display), so the same student sees `"3 of 4"`.

Both are defensible conventions, but they are inconsistent with each other and produce different numbers for the same progress state. A student who sees "2 of 4" on the map and then "3 of 4" on the page will be confused.

**Fix**: Align both to `currentIndex + 1` style (1-based "you are on segment N"). In `ModuleMap.tsx`:
```tsx
<ProgressBar
  label={`Module ${module.number} progress`}
  value={module.currentSegmentPosition + 1}
  max={module.segmentCount}
  showCount
/>
```
(The underlying `<progress>` value is visual only; `currentSegmentPosition + 1` correctly shows "on segment 3 of 4" rather than "passed segment 2 of 4".)

---

### [MINOR] Wrong FR reference in `module.api.ts` JSDoc

**File**: `web/src/features/module/module.api.ts:16`

```ts
 * (FR-5.2) and returns the updated module detail.
```

FR-5.2 is the code-activity "Check" feature (Parsons/fill-in), not position-saving. Position saving is **FR-2.5**.

**Fix**: Change `FR-5.2` to `FR-2.5`.

---

### [MINOR] `Finish module` button re-saves position without navigating away

**File**: `web/src/features/module/ModulePage.tsx:60–62`

When the student clicks "Finish module" (on the last segment), `handleNext()` calls `navigateTo(currentIndex + 1)`. Because of the clamp (`Math.min(currentIndex + 1, segments.length - 1)`), `clamped === currentIndex`, so the UI stays on the same last segment and fires another POST to save the same position. This does mark the module `complete` (which is correct), but the student receives no feedback that anything happened — no navigation, no success message, no visual change beyond the button going into `loading` state briefly.

From an acceptance criterion perspective, (d) "module completes" works correctly at the data level. But the UX after clicking "Finish module" is ambiguous: the student is still looking at the last segment of a now-complete module with no indication of what to do next.

**Fix**: After the mutation succeeds on the last segment, navigate back to the module map:
```tsx
const mutation = useMutation({
  mutationFn: (position: number) => savePosition(id, position),
  onSuccess: (data, position) => {
    void queryClient.invalidateQueries({ queryKey: ['modules'] })
    void queryClient.invalidateQueries({ queryKey: ['module', id] })
    if (isLast) void navigate('/')
  },
})
```
Or show a completion banner instead of/in addition to navigation. Either way, some post-completion feedback is needed.

---

### [MINOR] No test covers the all-modules-complete state on the map

**File**: `web/src/features/module/ModuleMap.test.tsx`

The test `'hides the Continue button when all modules are locked or complete'` uses `[completeModule, lockedModule]`. There is no test for the scenario where all 7 modules are complete — the student has finished the course. The Continue button would be hidden (correct), but there is also no "Course complete" message. This is a known gap worth a TODO comment at minimum.

This does not affect existing functionality and is noted here as a test coverage gap.

---

### [NITPICK] `_compute_status` return type annotation has a `# type: ignore`

**File**: `api/app/services/modules.py:73`

```python
return status  # type: ignore[return-value]
```

`status` is typed as `str` (from `progress.status`) even though `ModuleStatus` is a `Literal`. The `type: ignore` is sound (the seed and save_position enforce valid values), but a cast would be cleaner than a suppression:
```python
from typing import cast
return cast(ModuleStatus, status)
```
The `cast` documents the intent ("we trust the DB value here") without suppressing a whole class of mypy errors at that site.

---

### [NITPICK] `db` fixture does not dispose for Postgres test runs at teardown error path

**File**: `api/tests/conftest.py:33–59`

The `db` fixture does `engine.dispose()` at the end. If `Base.metadata.drop_all(engine)` raises (for Postgres, after the test body), `engine.dispose()` is never called because there is no `try/finally`. With SQLite this is not a problem (StaticPool is closed immediately by GC), but on Postgres it could leave a dangling connection.

**Fix**: Wrap the post-yield teardown in a `try/finally`:
```python
try:
    if TEST_DATABASE_URL:
        Base.metadata.drop_all(engine)
finally:
    engine.dispose()
```

---

## Acceptance Criteria Verification

| # | Criterion | Status |
|---|-----------|--------|
| (a) Module map shows state locked/open/in_progress/complete + duration | ✅ Pass — `ModuleMap` renders `Tag` for each status; `formatDuration` shows estimated minutes |
| (b) Module opens once previous complete; module 0 always open | ✅ Pass — `_compute_status` in service, backed by 5 tests in `test_modules.py` |
| (c) Module page shows goals then segments in order | ✅ Pass — goals rendered with `<Markdown>` before segments; segments ordered by `Segment.position` |
| (d) Current segment saved and returning resumes there | ✅ Pass — `savePosition` upserts on every navigation; `ModulePage` initialises from `currentSegmentPosition` |
| (e) text/worked_example segments render Markdown | ✅ Pass — `SegmentView` dispatches to `<Markdown>` for `text`, `worked_example`, and `refresher` |

---

## Security / User-Scoping Verification

| Check | Result |
|---|---|
| Every query scoped to `user.id` | ✅ `get_modules_for_user`, `get_module_detail`, `save_position` all filter by `user_id` |
| User A cannot read User B's progress | ✅ Tested by `test_user_b_sees_initial_locked_states_regardless_of_user_a_progress` and `test_user_a_position_does_not_bleed_into_user_b` |
| User A cannot write to User B's progress | ✅ `save_position` does `ModuleProgress.user_id == user_id`; the UniqueConstraint ensures one row per user+module |
| 401 for unauthenticated requests | ✅ All three endpoints use `CurrentUser`; three tests verify 401 |
| 403 for locked modules | ✅ `ModuleLocked` → 403; two tests verify this for GET and POST |
| 404 for missing modules | ✅ `ModuleNotFound` → 404; two tests verify this |
| No answer/solution leakage in `SegmentOut` | ✅ `SegmentOut` only exposes `activity_id` (an int), never activity config or answer |
| Markdown renderer is CSP-safe (no `dangerouslySetInnerHTML`, no `rehype-raw`) | ✅ `Markdown.tsx` uses `<ReactMarkdown>` only; Markdown.test.tsx verifies `<script>` in source is not injected |
| No raw HTML injection through goals/body fields | ✅ Confirmed by CSP test; react-markdown drops raw HTML nodes by default |

---

## Architecture / Conventions Verification

| Check | Result |
|---|---|
| Layered routers → services → models | ✅ Router handles HTTP; service handles business logic; models are plain SQLAlchemy |
| Router commits; service flushes | ✅ `save_position` calls `session.flush()`; router calls `session.commit()` |
| Schemas subclass `ApiModel` (camelCase, `extra="forbid"`) | ✅ All four schemas extend `ApiModel` |
| Migration 0007 is correct and reversible | ✅ `test_migrations_apply_from_scratch_and_match_the_models` passes; `downgrade()` is the exact reverse of `upgrade()` |
| One migration head | ✅ `test_there_is_exactly_one_head` passes |
| Models match migration | ✅ `alembic check` passes via `test_migrations` |
| Seed: merges by fixed id, never touches progress | ✅ `session.merge()` used; `ModuleProgress` rows not touched in `load()`; verified by `test_reseed_updates_module_content_and_leaves_progress_intact` |
| Frontend feature folder + `api()` client + TanStack Query conventions | ✅ `module.api.ts`, `module.types.ts`, `ModuleMap.tsx`, `ModulePage.tsx` all follow the established pattern |
| `react-markdown` pinned exact version | ✅ `"react-markdown": "10.1.0"` in `package.json` (no caret) |

---

## CI / Definition of Done

`scripts/check.sh` exits **0** (verified locally, Node v24.22.2, Python 3.13.2):
- web: format ✅, lint ✅ (0 warnings, 0 errors), 131 tests ✅, build ✅
- api: ruff format ✅, ruff check ✅, mypy strict ✅ (56 files), pytest 435 passed 1 skipped ✅
- Pre-existing SQLite ResourceWarning flaps fully resolved by Wave 4a engine-dispose fixes.

---

## Verdict

**Requires fixes** before merge.

**Must fix (Important items)**:

1. `PositionIn.segment_position: int = Field(ge=0)` — a negative value corrupts the DB row and can crash the ModulePage render on resume.
2. Fix the misleading `"1-based position"` comment in `ModulePage.tsx:52` — it's actively wrong and will confuse the next person touching this code.
3. Add a TODO comment (or a filter) to `get_module_detail` for the refresher-segment filtering that the SE §9 contract promises but is not implemented.
4. Document the `current_segment_position` deviation from SE §8 (`current_segment_id`) with an explicit comment explaining the trade-off.

Items 2–4 are documentation/comment-level fixes that cannot break anything. Item 1 is a one-line schema change. None of the four require a new migration or a logic change. The feature is functionally sound, all acceptance criteria are met, user-scoping is correctly enforced, CSP safety is verified, and CI is deterministically green.

**Minor items** (Continue button UX after Finish, progress-bar inconsistency, wrong FR reference, `%` icon) should be tracked but are not merge blockers for this story.

---

## Re-review — commit dcb6c89

**Scope**: Confirm the 4 Important and 3 Minor fixes applied in dcb6c89 are correct, and give a final verdict against FR-2.1/2.3/2.5/2.6 and the local DoD.

### Important items

**[IMPORTANT 1] `PositionIn.segment_position = Field(ge=0)` — ✅ Resolved**

`api/app/schemas/modules.py`: `from pydantic import Field` is imported and `segment_position: int = Field(ge=0)` is in place. The `PositionIn` docstring explicitly explains _why_ the constraint exists (negative value → `segments[-1]` crash on resume), which is better than the minimal fix requested.

`api/tests/test_modules.py`: `test_post_position_with_negative_segment_position_is_422` posts `{"segmentPosition": -1}` and asserts `status_code == 422`. The test is correctly placed in section 11 ("Input validation"), has a docstring linking back to the crash scenario, and passes (`436 passed, 1 skipped` in final check run). The guard is exercised before the service layer — no module lookup, no DB write.

**[IMPORTANT 2] Misleading "1-based" comment in `ModulePage.tsx` — ✅ Resolved**

The comment at `navigateTo` now reads:
```tsx
// segment.position is 0-based and equals clamped when segments are sequential,
// so sending it directly satisfies the backend contract (FR-2.5).
```
This is factually correct: segments are enforced to be `0, 1, …, n-1` by the seed validator, so `segments[clamped].position === clamped`. The old comment ("1-based position matches the segment's `position` field") is gone.

**[IMPORTANT 3] FR-8.1 refresher filtering TODO in `get_module_detail` — ✅ Resolved**

`api/app/services/modules.py`: a multi-line TODO comment sits immediately above the segment query, noting the SE §9 contract, that the diagnostic is out of scope, that refreshers are included for now, and the nuance that a refresher with no diagnostic rule should still be shown. Placed exactly where the filtering would go. No analogous TODO was added to `get_modules_for_user` (which only counts segments, not kinds) — that is correct; the SE §9 contract is about the detail endpoint.

**[IMPORTANT 4] SE §8 deviation (`current_segment_id` vs `current_segment_position`) — ✅ Resolved**

Comment added in both the model (`api/app/models/module.py`, `ModuleProgress.current_segment_position`) and the schema (`api/app/schemas/modules.py`, `ModuleOut.current_segment_position`). Both notes cite approved decision 5, the migration implication of future reordering, and the seed invariant. The schema comment is slightly more concise than the model comment — both are adequate. Having the note in two places (ORM definition and API shape) is better than one, since a developer working only on the frontend sees the schema version.

---

### Minor items

**[MINOR] `ModuleMap.tsx` `in_progress` icon `'%'` → `'◑'` — ✅ Resolved**

`statusDisplay` for `'in_progress'` now returns `icon: '◑'`. The half-filled circle is semantically consistent with the other single-character icons (`'○'`, `'✓'`).

**[MINOR] Progress-bar value now 1-based in `ModuleMap.tsx` — ✅ Resolved**

`ModuleRow` renders `value={module.currentSegmentPosition + 1}`. Both `ModuleMap` and `ModulePage` now display the same "you are on segment N of M" semantics. The `ModuleMap.test.tsx` progress-bar test only asserts presence (`getByRole('progressbar')`), not the count text, so no test expectation needed updating — confirmed correct.

**[MINOR] Wrong FR reference in `module.api.ts` JSDoc — ✅ Resolved**

`savePosition` JSDoc now reads `(FR-2.5)`. The old `FR-5.2` is gone.

---

### Tests and CI

`scripts/check.sh` exits **0** (re-verified, Node v24.22.2, Python 3.13.2):
- web: format ✅, lint ✅ (0 warnings, 0 errors), **131 tests** ✅ (12 test files), build ✅
- api: ruff format ✅, ruff check ✅, mypy strict ✅ (56 files), **436 passed, 1 skipped** ✅

The new test (`test_post_position_with_negative_segment_position_is_422`) is counted in the api total (436, up from 435 before the reviewer-fix commit).

---

### Deferred items — still acceptable

These were explicitly deferred and remain out of scope:

- **Finish-module UX** (`ModulePage.tsx`) — student stays on the last segment after clicking "Finish module" with no navigation or completion banner. Tracked as a future story UX improvement.
- **All-modules-complete test** (`ModuleMap.test.tsx`) — no test for the state where every module is `complete`. Coverage gap only; existing tests are not broken.
- **`cast` vs `# type: ignore`** (`services/modules.py:73`) — `_compute_status` still uses `# type: ignore[return-value]`. Sound but a nitpick.
- **conftest try/finally for Postgres teardown** (`api/tests/conftest.py`) — SQLite path is safe after the Wave 4a dispose fixes; Postgres teardown error path is still theoretically unsafe. Low real-world risk.

---

### Acceptance criteria — final check

| FR | Criterion | Status |
|---|---|---|
| FR-2.1 | Module map shows all modules with locked/open/in_progress/complete state | ✅ |
| FR-2.3 | Module page shows goals (Markdown) then segments in order | ✅ |
| FR-2.5 | Current segment position saved on every navigation; resumes correctly | ✅ (negative input now rejected at boundary) |
| FR-2.6 | Module completes when last segment reached; `completed_at` recorded | ✅ |

Local Definition of Done: tests green ✅ (131 web, 436 api), checks green ✅ (`scripts/check.sh` exit 0). Merge/PR out of scope.

---

### Final Verdict

**Ready to merge.**

All 4 Important items from the prior review are correctly resolved. All 3 quick Minor items are correctly resolved. The fixes are minimal, do not introduce new logic, and did not break any existing tests. `scripts/check.sh` exits 0 deterministically. The 4 deferred items are acceptable follow-ups for future stories.
