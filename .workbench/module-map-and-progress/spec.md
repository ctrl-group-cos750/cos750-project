# Module Map & Progress — As-Built Spec

## User Story

> As a student, I want to see the modules and pick up where I left off, so that I can work through the course in short sittings.

## Requirements Covered

| Req | Description |
|-----|-------------|
| FR-2.1 | Module map with states (locked/open/in_progress/complete) and estimated duration |
| FR-2.3 | Module page shows Markdown learning goals then ordered segments |
| FR-2.5 | Current segment position saved on every navigation; returning student resumes |
| FR-2.6 | Module completes when student reaches last segment; `completed_at` recorded |

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| AC-1 | Module map shows each module's state (locked/open/in_progress/complete) and estimated duration | ✅ |
| AC-2 | Sequential unlocking: module 0 always open; module N opens when module N-1 is complete | ✅ |
| AC-3 | Module page displays learning goals (Markdown) then segments in order | ✅ |
| AC-4 | Current segment position saved on every navigation; returning student resumes from saved position | ✅ |
| AC-5 | Text and worked_example segments render Markdown (react-markdown, CSP-safe) | ✅ |

---

## Data Model

### Module (table: `modules`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | Surrogate; seed fixtures use fixed ids 1–7 |
| `number` | int | 0–6, matching ID document module numbering |
| `slug` | str | URL-safe identifier (e.g. `warm-up`, `meet-bfs`) |
| `title` | str(200) | Real titles from ID document Table 4 |
| `goals` | Text | Markdown "By the end of this module you can …" |
| `estimated_minutes` | int | Shown on the module map |
| `position` | int | 0-based display order on the map |

### Segment (table: `segments`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | Surrogate; seed fixtures use fixed ids 1–13 |
| `module_id` | int FK → modules.id | Indexed |
| `position` | int | 0-based within module |
| `kind` | str(32) | `video` \| `text` \| `worked_example` \| `activity` \| `refresher` |
| `title` | str(200) | |
| `body` | Text, nullable | Markdown for `text`/`worked_example`; null for others |
| `skip_check_activity_id` | int FK → activities.id, nullable | FR-8.2 skip check |
| `refresher_for` | str, nullable | FR-8.1 diagnostic topic |
| `video_id` | int FK → videos.id, nullable | Set for `video` segments |
| `activity_id` | int FK → activities.id, nullable | Set for `activity` segments |

**Decision 1 (approved):** Segment owns `video_id` and `activity_id` (segment → content). Video also carries `segment_id` (content → segment), matching the SE §8 ER diagram. Both directions present.

### Video.segment_id (added column)

`segment_id: Mapped[int | None]` — nullable FK to `segments.id`, added to the existing `videos` table. Uses `use_alter=True` with explicit FK name `fk_videos_segment_id_segments` to break the circular `segments ↔ videos` dependency for Alembic/SQLAlchemy table sorting.

### ModuleProgress (table: `module_progress`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | Surrogate (decision 5) |
| `user_id` | int FK → users.id | Indexed |
| `module_id` | int FK → modules.id | Indexed |
| `status` | str(20), default `'open'` | `open` \| `in_progress` \| `complete` |
| `current_segment_position` | int, default 0 | 0-based last-reached segment position |
| `completed_at` | DateTime(tz), nullable | Set on first completion; never overwritten |

`UniqueConstraint("user_id", "module_id")` enforces one progress row per user+module.

**Decision 5 (approved):** Surrogate `id` PK + unique constraint, matching every other table in the project.

**SE §8 deviation (noted):** SE §8 specifies `current_segment_id` (FK to segments). Implementation uses `current_segment_position` (int) instead — simpler, no FK, but not robust to segment reordering. Seed enforces sequential 0-based positions. Documented in model and schema with comments.

### Migration

`20261105_0007_modules_segments_and_progress.py` — creates `modules`, `segments`, `module_progress` tables; adds `segment_id` column to `videos`. Written by hand (no Docker/autogenerate). Uses `batch_alter_table` for the circular FK on SQLite compatibility.

### Seed Fixtures

`api/app/seed/modules.json` — 7 modules (ids 1–7, numbers 0–6) with real titles/goals from ID document Table 4. 13 segments total (2 per module, 1 for module 6). All segment bodies are placeholders for Sprint 2. Kinds used: `text` and `worked_example` only. Segments nested under their module in JSON; `module_id` injected by a pre-validator.

**Decision 4 (approved):** Real titles and goals from the ID document; placeholder segment content.

---

## API Endpoints

All endpoints require authentication (`CurrentUser`). All queries scoped to `user.id`.

### GET /api/modules → `list[ModuleOut]`

Returns all modules in position order with per-student computed status.

| Status code | Condition |
|-------------|-----------|
| 200 | Success |
| 401 | Not authenticated |

Response shape (`ModuleOut`):
```
{ id, number, slug, title, goals, estimatedMinutes, status, segmentCount, currentSegmentPosition }
```

Three bulk queries (modules, progress rows, segment counts) — no N+1.

### GET /api/modules/{module_id} → `ModuleDetailOut`

Returns one module with ordered segments and student's status.

| Status code | Condition |
|-------------|-----------|
| 200 | Success |
| 401 | Not authenticated |
| 403 | Module is locked for this student |
| 404 | Module does not exist |

Response shape (`ModuleDetailOut`): `ModuleOut` + `segments: list[SegmentOut]`

`SegmentOut`:
```
{ id, position, kind, title, body, videoId, activityId }
```

### POST /api/modules/{module_id}/position → `ModuleDetailOut`

Saves the student's current segment position. Returns the updated module detail (200, not 201 — this is an upsert, not a new resource creation).

Request body (`PositionIn`):
```
{ segmentPosition: int }   // ge=0 enforced by Pydantic Field
```

| Status code | Condition |
|-------------|-----------|
| 200 | Position saved |
| 401 | Not authenticated |
| 403 | Module is locked |
| 404 | Module does not exist |
| 422 | `segmentPosition < 0` (Pydantic validation) |

---

## Unlock & Status Logic

### Status computation (`_compute_status`)

1. If a `ModuleProgress` row exists with status `complete`, `in_progress`, or `open` → use it.
2. No row: module 0 or previous module complete → `"open"`; otherwise → `"locked"`.

### Completion (`save_position`)

```
segment_count = count of segments for the module
last_index    = max(segment_count - 1, 0)
is_complete   = segment_count > 0 AND segment_position >= last_index
```

If complete: `status = 'complete'`, `completed_at = now(UTC)` (only on first completion).
Otherwise: `status = 'in_progress'`.

**Decision 3 (approved):** Completion triggers on reaching the last segment position. Activity-gating is deferred.

> **TODO:** When the activity story is implemented, gate completion on all required activities in the module being answered correctly. Until then, reaching the last segment is sufficient.

---

## Frontend

### ModuleMap (replaces HomePage, route: `/`)

- Fetches `GET /api/modules` via TanStack Query (`queryKey: ['modules']`).
- Renders page heading "Graphs and breadth-first search", total estimated duration, and a card list.
- Each module card shows: number, title, estimated duration, status `Tag` (locked → neutral/🔒, open → accent/○, in_progress → warning/◑, complete → success/✓).
- In-progress modules show a `ProgressBar` with 1-based count (`currentSegmentPosition + 1` of `segmentCount`).
- **Whole card is clickable** for open/in_progress/complete modules: `<Link to="/modules/:id">` wraps the `<Card>`. Locked module cards are not wrapped in a link and are non-interactive (opacity 0.6).
- "Continue module N →" `Button` targets the first in-progress module, else the first open module. Remains as a shortcut alongside per-card links.
- CSS Modules for layout (`ModuleMap.module.css`); `.cardLink` resets anchor styling.

### ModulePage (route: `/modules/:moduleId`)

- Fetches `GET /api/modules/:id` via TanStack Query.
- Displays module title, learning goals rendered as `<Markdown>` (FR-2.3).
- `ProgressBar` shows "Segment X of Y" (1-based).
- `SegmentView` dispatches on `segment.kind`:
  - `text` / `worked_example` / `refresher` → `<Markdown>{segment.body}</Markdown>`
  - `video` → `<Link to="/videos/:videoId">▶ Watch video</Link>`
  - `activity` → placeholder `Alert` ("Activity — coming in a future story.")
- Previous/Next navigation. `savePosition` called via `useMutation` on every navigation.
- **Finish module behaviour:** On the last segment, the button reads "Finish module". Clicking it saves the final position (backend marks module complete). On mutation success, if the saved position equals the last segment's position, `navigate('/')` sends the student back to the module map. The map re-fetches and shows the module as complete with the next module unlocked.
- Segment index initialises from `currentSegmentPosition` (server state); subsequent navigation is local state.

### SegmentView

Exhaustive `switch` on `segment.kind` with `never` default for type safety.

### Markdown Component (`web/src/components/Markdown.tsx`)

- Thin wrapper around `react-markdown` 10.1.0 (exact pinned version).
- Renders Markdown to React elements — no `dangerouslySetInnerHTML`, no `rehype-raw`.
- CSP-safe: raw HTML in markdown source (e.g. `<script>`) is dropped by the remark/rehype pipeline by default.
- Scoped prose styling via CSS Modules (`Markdown.module.css`).
- Exported from `web/src/components/index.ts`.

**Decision 2 (approved):** `react-markdown` chosen for CSP safety (renders to React elements natively).

### Routing Changes

- `web/src/App.tsx`: added `<Route path="modules/:moduleId" element={<ModulePage />} />` inside `RequireAuth/SignedInLayout`.
- `web/src/pages/HomePage.tsx`: replaced placeholder with `<ModuleMap />`.
- `web/src/pages/SignedInLayout.tsx`: added "Modules" link in header nav for all signed-in users.

---

## Approved Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Segment owns `video_id`/`activity_id`; Video also carries `segment_id` | Both FK directions present per SE §8 ER diagram; avoids N+1 queries |
| 2 | Use `react-markdown` 10.1.0 | Renders to React elements (no innerHTML); inherently CSP-safe |
| 3 | Mark complete on reaching last segment position (activity-gating deferred) | Activity renderer out of scope; TODO placed for future gating |
| 4 | Real titles/goals from ID document; placeholder segment content | Module map looks correct on staging immediately |
| 5 | Surrogate `id` PK on ModuleProgress + UniqueConstraint | Matches project convention (every table uses `id` PK) |

---

## Post-Review Bug Fixes (spec'd behaviour)

### Bug Fix 1: Finish-module navigation

**Before:** Clicking "Finish module" on the last segment saved the position and marked the module complete on the backend, but the student stayed on the same page with no visual feedback.

**Spec'd behaviour:** Clicking "Finish module" saves the final position (module marked complete on backend). The `useMutation.onSuccess` callback checks if the saved position equals the last segment's position; if so, it calls `navigate('/')`. The student is sent back to the module map, where the module shows "complete" and the next module is unlocked.

### Bug Fix 2: Clickable module cards

**Before:** Only the "Continue" button at the bottom of the map navigated to a module. Clicking a module card did nothing despite the hover-lift CSS.

**Spec'd behaviour:** Open, in-progress, and complete module cards are wrapped in `<Link to="/modules/:id">`. The entire card surface is a clickable navigation target. Locked module cards are not wrapped in a link and remain non-interactive. The "Continue" button remains as a shortcut for the first actionable module.

---

## Test Coverage

### Backend (436 passed, 1 skipped)

- `test_modules.py` — 22 tests: initial states, segment ordering, 403/404/401 responses, position saving, completion, cascading unlock, user-scoping (two-user isolation), negative position → 422.
- `test_seed.py` — 11 new tests: fixture validation, sequential positions, invalid kinds/bodies refused, duplicate ids refused, reseed preserves progress.
- `test_migrations.py` — confirms one Alembic head, migration applies from scratch and matches models.

### Frontend (134 passed)

- `ModuleMap.test.tsx` — 16 tests: status tags, locked/open affordances, card links (open → link, locked → no link), Continue button targeting, loading/error states, duration and progress.
- `ModulePage.test.tsx` — 19 tests: goals rendering, segment kinds (text/worked_example/video/activity), navigation + position saving, finish-module navigation to map, resume from saved position, loading/error states.
- `Markdown.test.tsx` — 5 tests: headings, paragraphs, code blocks, inline code, CSP safety (script tags dropped).
- `App.test.tsx` and `auth.test.tsx` — updated to expect the module map heading instead of the old placeholder.

### CI

`scripts/check.sh` exits 0. Web: format, lint, 134 tests, build. API: ruff format, ruff check, mypy strict (56 files), 436 passed + 1 skipped.

Also fixed 3 pre-existing `ResourceWarning` sources (unclosed SQLite engines in `migrations/env.py`, `test_migrations.py`, `conftest.py`) that caused non-deterministic test failures across the whole suite.

---

## Deferred / Out-of-Scope Follow-Ups

| Item | Notes |
|------|-------|
| "Course complete" message/test | No message or test for when all 7 modules are complete. The Continue button hides, but there is no congratulatory UI. |
| Refresher diagnostic filtering (FR-8.1) | SE §9 says GET /modules/{id} leaves out refreshers the diagnostic ruled out. Diagnostic does not exist yet. TODO comment placed at query site. |
| Activity-gated completion | Completion currently triggers on reaching last segment position. When activity renderer is built, gate on all required activities being passed. TODO comment in `save_position`. |
| Activity renderer | `activity` segments show a placeholder Alert. Full renderer is a separate story. |
| Real segment content for Sprint 2 | All 13 segment bodies are placeholders. Sprint 2 delivers real Markdown and links video/activity segments. |
| `_compute_status` cast vs type-ignore | `services/modules.py` uses `# type: ignore[return-value]` instead of `cast(ModuleStatus, status)`. Functional but a nitpick. |
