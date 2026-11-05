# Task: Module Map, Module Page, and Progress Tracking

## User Request

> As a student, I want to see the modules and pick up where I left off, so that I can work through the course in short sittings.

Requirements: FR-2.1, FR-2.3, FR-2.5, FR-2.6.  
Acceptance criteria: module map with states/duration; sequential unlocking (module 0 always open); module page with goals + ordered segments; saved position with resume; Markdown rendering for text/worked-example segments.  
Scope: modules + segments + progress + module map only. NOT activity renderer, BFS visualiser, mastery, or points. Video player already exists. Link to/embed existing components where they exist.

## Codebase Summary

- **Stack**:
  - Backend: Python 3.12, FastAPI 0.162.0, SQLAlchemy 2.1.6, Alembic 1.20.1, Pydantic v2, pytest 9.2.0, ruff 0.17.3, mypy 2.4.1 (strict)
  - Frontend: React 19.3.1, TypeScript 7.0.2, Vite 8.3.5, TanStack Query 5.105.1, react-router 8.5.1, Tailwind CSS 4.3.4, Vitest 5.0.5, React Testing Library 16.3.3, Playwright 1.64.1 (dev dep, no e2e/ dir yet)
  - DB: PostgreSQL 18 (tests use in-memory SQLite)

- **Structure**:
  - `api/app/models/` — SQLAlchemy models, imported in `__init__.py` for Alembic
  - `api/app/schemas/` — Pydantic schemas subclassing `ApiModel` (camelCase JSON)
  - `api/app/routers/` — FastAPI routers, registered in `api/app/main.py`
  - `api/app/services/` — Business logic (checking, bfs, videos)
  - `api/app/seed/` — JSON fixture loader with Pydantic validation
  - `api/app/auth.py` — `CurrentUser` dep scoped to `user.id`
  - `api/app/db.py` — `DbSession` dep, `Base` for models
  - `api/migrations/versions/` — Alembic migrations, latest `0006`
  - `web/src/features/<name>/` — Feature folders with `<name>.api.ts`
  - `web/src/components/` — Shared UI kit (Button, Card, Tag, ProgressBar, Spinner, Alert, MasteryStatus)
  - `web/src/pages/` — Layout and pages (HomePage is placeholder for module map)
  - `web/src/auth/` — Session hooks (`useCurrentUser`), route guards
  - `web/src/api/client.ts` — Shared `api<T>()` function
  - `web/src/test/app.tsx` — `fakeApi()` + `renderApp()` test helpers

- **Conventions**:
  - **Models**: use `Mapped[T]` + `mapped_column()`, `ForeignKey` strings to table names, import in `models/__init__.py`
  - **Schemas**: subclass `ApiModel`, camelCase aliases, `extra="forbid"`, `from_attributes=True`
  - **Routers**: `APIRouter(prefix="/api/<resource>", tags=[...])`, use `CurrentUser` and `DbSession` deps, explicit `session.commit()`
  - **Services**: pure functions or service modules, imported by routers
  - **Seed**: JSON fixtures in `api/app/seed/`, `FixtureFile` Pydantic model, `read_fixtures()` validates, `load()` merges by fixed id (never touches attempts)
  - **Frontend API**: typed functions in `<feature>.api.ts` calling `api<T>(path, opts)`
  - **Frontend tests**: Vitest + RTL, `fakeApi({user, overrides})` stubs `fetch`, `renderApp(path)` renders full app
  - **CSS**: Tailwind utility classes (newer code) and CSS Modules (older components); coexist
  - **Migrations**: named `YYYYMMDD_NNNN_description.py`, revision string = `"NNNN"`, sequential

- **Critical Findings**:
  1. **No Markdown library installed.** AC 5 requires rendering Markdown for text/worked-example segments. Must add `react-markdown` (or similar). The CSP (`script-src 'self'`) forbids inline scripts/unsafe HTML, so the renderer must not inject raw HTML — `react-markdown` renders to React elements natively, which is safe.
  2. **Video model has `segment_id` comment**: `"segment_id is added then"` referencing #14/#15 — this story IS that moment. Need to add `segment_id` FK on `Video` and wire `Video ↔ Segment`.
  3. **Latest migration is `0006`.** New migration will be `0007`.
  4. **Seed system currently handles `activities` and `graphs` only.** Must extend to also handle `modules` and `segments` (with their own fixture schema and validation).
  5. **HomePage.tsx** is an explicit placeholder: `"Placeholder until the module map (#15) replaces it."` — will be replaced with the ModuleMap.

## Relevant Files

### Must Read Before Implementation

**Backend — Models & DB:**
- `api/app/models/__init__.py` — register new models here
- `api/app/models/video.py` — has the `segment_id` TODO, add FK here
- `api/app/models/activity.py` — Activity, Attempt, Hint, HintView patterns
- `api/app/models/user.py` — User model shape
- `api/app/db.py` — `Base`, `DbSession`, engine config

**Backend — Schemas:**
- `api/app/schemas/base.py` — `ApiModel` base class
- `api/app/schemas/activities.py` — ActivityOut, schema conventions
- `api/app/schemas/videos.py` — VideoOut, CheckpointOut patterns

**Backend — Routers & Services:**
- `api/app/routers/activities.py` — router pattern, `CurrentUser`/`DbSession` usage
- `api/app/routers/videos.py` — joined queries, response building pattern
- `api/app/services/videos.py` — service layer pattern
- `api/app/main.py` — router registration

**Backend — Seed:**
- `api/app/seed/__init__.py` — fixture loading pattern, validation, `SHAPES` dict, `FixtureFile`
- `api/app/seed/graphs.json` — fixture JSON shape
- `api/app/seed/__main__.py` — invocation

**Backend — Auth:**
- `api/app/auth.py` — `CurrentUser` dep

**Backend — Migrations:**
- `api/migrations/versions/20261105_0006_graph_scenarios.py` — latest migration, naming convention
- `api/migrations/env.py` — how test URLs are passed

**Backend — Tests:**
- `api/tests/conftest.py` — `db` fixture, `client` fixture, SQLite override
- `api/tests/test_seed.py` — seed test pattern
- `api/tests/test_migrations.py` — migration test (will auto-check new model)

**Frontend — Routing & Layout:**
- `web/src/App.tsx` — route definitions, `RequireAuth`, `SignedInLayout`
- `web/src/pages/SignedInLayout.tsx` — header with nav links
- `web/src/pages/HomePage.tsx` — placeholder to replace

**Frontend — API & Feature Patterns:**
- `web/src/api/client.ts` — `api<T>()` function
- `web/src/features/video/video.api.ts` — feature API file pattern
- `web/src/features/video/VideoPage.tsx` — page using `useQuery` + feature components
- `web/src/features/video/NarratedVideoPlayer.tsx` — component to embed for video segments
- `web/src/features/video/video.types.ts` — type definitions

**Frontend — Shared UI:**
- `web/src/components/index.ts` — available exports (Card, Tag, ProgressBar, Spinner, Alert, etc.)
- `web/src/components/ProgressBar.tsx` — reusable progress bar

**Frontend — Tests:**
- `web/src/App.test.tsx` — routing test pattern with `fakeApi`, `renderApp`
- `web/src/test/app.tsx` — test helpers

**Docs:**
- `docs/se/se-document.md` — §8 Data Model, §9 API Design, §11 Frontend Component Breakdown
- `web/security-headers.conf` — CSP rules (affects Markdown renderer choice)
- `web/package.json` — dependencies (confirm no markdown lib)

## Execution Plan

### Wave 1: Backend Models + Migration + Seed Extension (foundation — everything depends on this)

| Sub-task | Agent | Details |
|----------|-------|---------|
| 1a. Create `Module` and `Segment` models, add `segment_id` FK to `Video`, create `ModuleProgress` model | developer | **Files to create:** `api/app/models/module.py` (Module, Segment, ModuleProgress). **Files to modify:** `api/app/models/video.py` (add `segment_id: Mapped[int \| None] = mapped_column(ForeignKey("segments.id"), nullable=True)`), `api/app/models/__init__.py` (import Module, Segment, ModuleProgress). **Shapes from SE §8:** Module(`id`, `number` 0–6, `slug`, `title`, `goals` Text, `estimated_minutes` int, `position` int). Segment(`id`, `module_id` FK→modules, `position` int, `kind` String(32) one of `video\|text\|worked_example\|activity\|refresher`, `title` String(200), `body` Text nullable — Markdown for text/worked_example, `skip_check_activity_id` FK→activities nullable, `refresher_for` String nullable, `video_id` FK→videos nullable, `activity_id` FK→activities nullable). ModuleProgress(`id`, `user_id` FK→users, `module_id` FK→modules, `status` String(20) default `"open"`, `current_segment_position` int default 0, `completed_at` DateTime nullable, UniqueConstraint on user_id+module_id). Video: add `segment_id` FK→segments nullable (keep backward-compatible). **Conventions:** use `Mapped[T]`, `mapped_column()`, docstrings citing SE document sections. |
| 1b. Generate Alembic migration `0007` | developer | Run `alembic revision --autogenerate -m "modules segments and progress"`. Review generated file: creates `modules`, `segments`, `module_progress` tables, adds `segment_id` column to `videos`. Name: `20261105_0007_modules_segments_and_progress.py`. Verify it applies from scratch with existing migration tests (they auto-check). |
| 1c. Create module/segment Pydantic schemas | developer | **File to create:** `api/app/schemas/modules.py`. Schemas: `ModuleOut` (id, number, slug, title, goals, estimatedMinutes, status — the student's status injected at query time, segmentCount, currentSegmentPosition), `SegmentOut` (id, position, kind, title, body — only for text/worked_example, videoId — only for video segments, activityId — only for activity segments), `ModuleDetailOut` (extends ModuleOut with `segments: list[SegmentOut]`), `PositionIn` (segmentPosition: int). All subclass `ApiModel`. |
| 1d. Extend seed system for modules + segments fixtures | developer | **File to create:** `api/app/seed/modules.json` — placeholder fixture with 7 modules (id 1–7, number 0–6) each with 1–2 placeholder segments. **Files to modify:** `api/app/seed/__init__.py` — add `ModuleFixture`, `SegmentFixture` Pydantic models with validation (kind must be valid, video segments need video_id, text/worked_example need body, etc.), add `modules` field to `FixtureFile`, extend `load()` to merge modules and segments by fixed id. Segments reference their module by `module_id`. Validation: segment kinds checked, positions sequential, module numbers 0–6. Follow existing pattern: `session.merge()` for upsert, never touch progress. |
| 1e. Backend unit + seed tests | developer | **File to modify:** `api/tests/test_seed.py` — add tests for module/segment fixtures: valid fixture loads, invalid kinds refused, duplicate module ids refused, segment referencing unknown module refused, a rerun updates content without touching progress rows. **Check:** `pytest -q` passes, `mypy` passes, `ruff check` passes. |

**Wave 1 acceptance:** `alembic upgrade head` succeeds from scratch on SQLite. `test_migrations.py` passes (models match migration, one head). `test_seed.py` passes with new module/segment tests. `mypy --strict` and `ruff` clean. `python -m app.seed` loads the placeholder modules fixture.

---

### Wave 2: Backend API Endpoints + Service Layer (depends on Wave 1 models)

| Sub-task | Agent | Details |
|----------|-------|---------|
| 2a. Create modules service | developer | **File to create:** `api/app/services/modules.py`. Functions: `get_modules_for_user(session, user_id) → list[dict]` — returns all modules with the student's status computed from `ModuleProgress` (locked/open/in_progress/complete). Logic: module 0 always open; module N open if module N-1 complete; a module with a `ModuleProgress` row is its status; a module without one is `"locked"` unless it should be open. `get_module_detail(session, user_id, module_id) → dict` — the module + its segments in position order + the student's current position. `save_position(session, user_id, module_id, segment_position) → None` — upsert `ModuleProgress` row, set `current_segment_position` and `status="in_progress"` (or `"complete"` if it's the last segment). When a module completes, check if the next module should become open. |
| 2b. Create modules router | developer | **File to create:** `api/app/routers/modules.py`. Endpoints per SE §9: `GET /api/modules` (user) → list of `ModuleOut` with states; `GET /api/modules/{module_id}` (user) → `ModuleDetailOut` with segments and position; `POST /api/modules/{module_id}/position` (user, body `PositionIn`) → save position. All scoped to `CurrentUser`. 404 if module not found. 403 if module is locked. **File to modify:** `api/app/main.py` — `app.include_router(modules.router)`. |
| 2c. Backend API tests | developer | **File to create:** `api/tests/test_modules.py`. Tests: (1) `GET /api/modules` returns all 7 modules with correct initial states (module 0 open, rest locked). (2) `GET /api/modules/{id}` returns segments in order with goals. (3) `GET /api/modules/{id}` returns 403 for a locked module. (4) `POST /api/modules/{id}/position` saves position and returns 200. (5) Completing last segment marks module complete. (6) Completing module N-1 opens module N. (7) Position is scoped to user (user A's position doesn't affect user B). (8) Returning student sees their saved position. Uses `db` fixture from conftest, creates modules/segments directly or via seed. **Check:** `pytest -q` passes, `mypy` passes, `ruff` clean. |

**Wave 2 acceptance:** All 3 endpoints work. API tests pass. `mypy --strict` and `ruff` clean. `GET /api/modules` returns proper states. `POST .../position` persists across requests. Module unlocking logic correct.

---

### Wave 3: Frontend — Module Map, Module Page, Markdown Component (depends on Wave 2 API; can parallelise 3a and 3b/3c within limits)

| Sub-task | Agent | Details |
|----------|-------|---------|
| 3a. Install `react-markdown` + create `Markdown` component | developer | **File to modify:** `web/package.json` — add `react-markdown` at a pinned exact version (e.g. `"react-markdown": "10.1.0"` — verify latest stable via Context7). `react-markdown` renders Markdown to React elements (no `dangerouslySetInnerHTML`), so it's CSP-safe. **File to create:** `web/src/components/Markdown.tsx` — a thin wrapper: `export function Markdown({ children }: { children: string }) { return <ReactMarkdown>{children}</ReactMarkdown> }`. Add appropriate className for prose styling. **File to modify:** `web/src/components/index.ts` — export `Markdown`. **File to create:** `web/src/components/Markdown.test.tsx` — renders heading, paragraph, code block; does NOT render raw HTML script tags. Run `npm install` after adding. |
| 3b. Create module feature (API layer + types) | developer | **File to create:** `web/src/features/module/module.types.ts` — types: `ModuleStatus = "locked" \| "open" \| "in_progress" \| "complete"`, `ModuleSummary` (id, number, slug, title, goals, estimatedMinutes, status, segmentCount, currentSegmentPosition), `Segment` (id, position, kind, title, body, videoId, activityId), `ModuleDetail` (extends ModuleSummary with segments). **File to create:** `web/src/features/module/module.api.ts` — `fetchModules(): Promise<ModuleSummary[]>` calling `GET /api/modules`, `fetchModule(id: number): Promise<ModuleDetail>` calling `GET /api/modules/${id}`, `savePosition(moduleId: number, segmentPosition: number): Promise<void>` calling `POST /api/modules/${moduleId}/position`. Follow `video.api.ts` pattern. |
| 3c. Create ModuleMap page (replaces HomePage) | developer | **File to create:** `web/src/features/module/ModuleMap.tsx`. Uses `useQuery` to fetch modules. Renders: page heading ("Graphs and breadth-first search"), each module as a card/row showing: number, title, estimated duration, status Tag (locked/open/in progress/complete using the existing `Tag` component with appropriate tones), current segment progress (using `ProgressBar` for in-progress modules). A "Continue" button linking to the in-progress or first-open module. Locked modules shown but not clickable. Per SE §11 wireframe. **File to create:** `web/src/features/module/ModuleMap.module.css` (or use Tailwind — match existing newer patterns). **File to modify:** `web/src/pages/HomePage.tsx` — replace placeholder with `ModuleMap` import (or redirect). Alternatively, rename the route's element. **File to modify:** `web/src/App.tsx` — update index route to render ModuleMap (via HomePage or directly). |
| 3d. Create ModulePage | developer | **File to create:** `web/src/features/module/ModulePage.tsx`. Route: `/modules/:moduleId`. Uses `useQuery` to fetch module detail. Shows: module title + goals (rendered as Markdown via new `Markdown` component — FR-2.3), segment list with current position highlighted, progress bar (segment X of Y). `SegmentView` sub-component picks the right renderer per segment kind: `text` / `worked_example` → `Markdown` component rendering `segment.body`; `video` → embed `NarratedVideoPlayer` (import from `features/video/`) using `segment.videoId`; `activity` → placeholder link/message ("Activity — coming in a future story") since activity renderer is out of scope. Navigation: Previous/Next buttons. On entering a segment, call `savePosition` (FR-2.5). On reaching last segment + navigating forward, module completes. **File to create:** `web/src/features/module/SegmentView.tsx` — dispatches by `segment.kind`. **File to modify:** `web/src/App.tsx` — add route `<Route path="modules/:moduleId" element={<ModulePage />} />` inside the `RequireAuth` layout. **File to modify:** `web/src/pages/SignedInLayout.tsx` — add "Modules" link to header nav (alongside existing staff "Videos" link). |
| 3e. Frontend tests for module feature | developer | **File to create:** `web/src/features/module/ModuleMap.test.tsx`. Tests: (1) shows all 7 modules with correct status tags. (2) module 0 is open, rest locked. (3) clicking "Continue" navigates to the right module. (4) locked modules are not clickable. Use `fakeApi` with module overrides. **File to create:** `web/src/features/module/ModulePage.test.tsx`. Tests: (1) shows module goals. (2) shows segments in order. (3) text segment renders Markdown. (4) saves position when navigating. (5) shows 403 redirect/message for locked modules. **File to modify:** `web/src/App.test.tsx` — update the home page test (it currently expects "Welcome, Ada" heading and API status text; the ModuleMap will change what the home route renders). **File to modify:** `web/src/test/app.tsx` — add `GET /api/modules` and `GET /api/modules/:id` to `fakeApi` routes. **Check:** `npm test -- --silent` passes, `npm run lint` passes, `npm run build` passes. |

**Wave 3 acceptance:** The module map renders at `/` (replacing placeholder). Each module shows state and duration. Clicking a module opens `/modules/:id`. The module page shows goals (Markdown) and segments. Text/worked-example segments render Markdown. Video segments embed the existing player. Position is saved on navigation. All frontend tests pass. `npm run build` succeeds (types OK). `npm run lint` + `npm run format:check` clean.

---

### Wave 4: Integration Verification + Review

| Sub-task | Agent | Details |
|----------|-------|---------|
| 4a. Full CI check | developer | Run `scripts/check.sh` from repo root. Fix any failures. This runs: web format, lint, test, build; api format, lint, mypy, pytest. Ensure `test_migrations.py` still passes (model ↔ migration match, one head). Ensure `test_seed.py` still passes with new module fixtures. |
| 4b. Review all changes | reviewer | Full review against the plan, SE document requirements (FR-2.1, FR-2.3, FR-2.5, FR-2.6), acceptance criteria, and codebase conventions. Check: (1) Models match SE §8 entity definitions. (2) API matches SE §9 endpoint table. (3) Schemas use `ApiModel`, camelCase. (4) Router uses `CurrentUser` + `DbSession`. (5) Seed follows existing pattern. (6) Frontend follows feature folder convention. (7) No `solution`/`answer` leaks. (8) All queries scoped to `user.id`. (9) Markdown renderer is CSP-safe. (10) Tests are meaningful. (11) No unused imports or dead code. (12) Migration is correct and reversible. |

**Wave 4 acceptance:** `scripts/check.sh` exits 0. Reviewer signs off. Local DoD met: tests green, checks green. Ready for PR (PR itself is out of scope).

## Files Expected to Change

### New Files
- `api/app/models/module.py` — Module, Segment, ModuleProgress models
- `api/app/schemas/modules.py` — ModuleOut, SegmentOut, ModuleDetailOut, PositionIn
- `api/app/services/modules.py` — module listing, detail, position saving, unlock logic
- `api/app/routers/modules.py` — GET /api/modules, GET /api/modules/{id}, POST /api/modules/{id}/position
- `api/app/seed/modules.json` — placeholder module + segment fixture data
- `api/migrations/versions/20261105_0007_modules_segments_and_progress.py` — migration
- `api/tests/test_modules.py` — API + service tests
- `web/src/components/Markdown.tsx` — Markdown renderer component
- `web/src/components/Markdown.test.tsx` — Markdown component tests
- `web/src/features/module/module.types.ts` — TypeScript types
- `web/src/features/module/module.api.ts` — API functions
- `web/src/features/module/ModuleMap.tsx` — Module map page
- `web/src/features/module/ModulePage.tsx` — Module detail page
- `web/src/features/module/SegmentView.tsx` — Segment kind dispatcher
- `web/src/features/module/ModuleMap.test.tsx` — Module map tests
- `web/src/features/module/ModulePage.test.tsx` — Module page tests

### Modified Files
- `api/app/models/__init__.py` — import Module, Segment, ModuleProgress
- `api/app/models/video.py` — add `segment_id` FK column
- `api/app/seed/__init__.py` — add module/segment fixture schemas + loading
- `api/app/main.py` — register modules router
- `api/tests/test_seed.py` — add module/segment seed validation tests
- `web/package.json` + `web/package-lock.json` — add `react-markdown` dependency
- `web/src/components/index.ts` — export Markdown
- `web/src/App.tsx` — add `/modules/:moduleId` route
- `web/src/pages/HomePage.tsx` — replace placeholder with ModuleMap (or remove and point route directly)
- `web/src/pages/SignedInLayout.tsx` — add "Modules" nav link
- `web/src/App.test.tsx` — update home page expectations
- `web/src/test/app.tsx` — add module API stubs to `fakeApi`
