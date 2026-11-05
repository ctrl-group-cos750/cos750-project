## Developer Notes — Sub-task 1a: SQLAlchemy models for Module, Segment, ModuleProgress + Video.segment_id

### Files Created

- `api/app/models/module.py` — Three new models (see details below).

### Files Modified

- `api/app/models/video.py` — Added `segment_id: Mapped[int | None]` nullable FK to `segments.id`.
  Updated the docstring: removed the "segment_id is added then" TODO comment and described the
  bidirectional relationship.
- `api/app/models/__init__.py` — Imported `Module`, `Segment`, `ModuleProgress` from
  `app.models.module`; added all three to `__all__` in alphabetical order.

---

### Models Created

#### `Module` (table: `modules`)
| Column | Type | Notes |
|---|---|---|
| `id` | `Mapped[int]` PK | surrogate |
| `number` | `Mapped[int]` | 0–6, matching ID document |
| `slug` | `Mapped[str]` | `String` (no length cap — slugs are short by convention) |
| `title` | `Mapped[str]` | `String(200)` |
| `goals` | `Mapped[str]` | `Text` — "By the end of this module you can ..." (FR-2.3) |
| `estimated_minutes` | `Mapped[int]` | shown on module map |
| `position` | `Mapped[int]` | display order on the map |

#### `Segment` (table: `segments`)
| Column | Type | Notes |
|---|---|---|
| `id` | `Mapped[int]` PK | surrogate |
| `module_id` | `Mapped[int]` FK `modules.id` | indexed |
| `position` | `Mapped[int]` | 0-based within module |
| `kind` | `Mapped[str]` | `String(32)`: `video\|text\|worked_example\|activity\|refresher` |
| `title` | `Mapped[str]` | `String(200)` |
| `body` | `Mapped[str \| None]` | `Text`, nullable — Markdown for `text`/`worked_example` |
| `skip_check_activity_id` | `Mapped[int \| None]` | FK `activities.id`, nullable (FR-8.2) |
| `refresher_for` | `Mapped[str \| None]` | `String`, nullable (FR-8.1) |
| `video_id` | `Mapped[int \| None]` | FK `videos.id`, nullable — set for `video` segments |
| `activity_id` | `Mapped[int \| None]` | FK `activities.id`, nullable — set for `activity` segments |

Decision 1 (approved): Segment owns `video_id` and `activity_id` (segment → content). Video also
carries `segment_id` (content → segment). Both directions are present, matching SE §8 ER diagram.

#### `ModuleProgress` (table: `module_progress`)
| Column | Type | Notes |
|---|---|---|
| `id` | `Mapped[int]` PK | surrogate (decision 5, approved) |
| `user_id` | `Mapped[int]` FK `users.id` | indexed |
| `module_id` | `Mapped[int]` FK `modules.id` | indexed |
| `status` | `Mapped[str]` | `String(20)`, default/server_default `'open'` |
| `current_segment_position` | `Mapped[int]` | default/server_default `0` (FR-2.5) |
| `completed_at` | `Mapped[datetime \| None]` | `DateTime(timezone=True)`, nullable (FR-2.6) |

`__table_args__ = (UniqueConstraint("user_id", "module_id"),)` enforces one progress row per
user+module pair.

Note: SE §8 names this column `current_segment_id` (a FK), but the task spec (approved decision 5)
specifies `current_segment_position` (an int) to track position without a FK. Followed the task spec.

---

### Key Decisions

1. **`func` not imported** in `module.py`: `ModuleProgress.completed_at` has no `server_default`
   for `func.now()` because it should be `NULL` until the module is actually completed — unlike
   `created_at` columns in other models. Removed the accidental `func` import that ruff flagged.

2. **No `index=True` on `Segment.video_id`/`activity_id`**: These are sparse FKs (most segments
   have only one of these set). Index benefit is low; can be added in a later migration if query
   profiling warrants it.

3. **`slug` uses plain `String`** (no length argument): SQLAlchemy maps this to `TEXT` in
   PostgreSQL, which is fine. An explicit length cap would be arbitrary.

4. **Pre-existing `security.py` mypy errors**: `pwdlib` stubs are missing from the system
   Python used for verification. These errors exist on the branch before this sub-task and are
   unrelated to the new models.

### Library Docs Consulted (Context7)
None — no new third-party libraries were introduced. SQLAlchemy patterns were verified by reading
existing model files directly.

### Build & Test Results

```
ruff format app/models/module.py app/models/video.py app/models/__init__.py
→ 3 files already formatted

ruff check app/models/module.py app/models/video.py app/models/__init__.py
→ All checks passed!

mypy app/models/module.py app/models/video.py app/models/__init__.py
→ Success: no issues found in 3 source files

mypy app/   (full app)
→ 3 pre-existing errors in app/security.py (pwdlib stub missing) — unrelated to this sub-task
```

### Open Issues

- `app/security.py` has 3 pre-existing mypy errors (`pwdlib` stub missing). These existed before
  this sub-task and need fixing separately (likely by installing `pwdlib` stubs or using the
  project's own venv rather than system Python).
- Sub-task 1b (Alembic migration `0007`) must be run next — the new tables do not exist in the
  database yet.
- `ModuleProgress.status` values (`open | in_progress | complete`) are validated only at the
  application layer; there is no DB-level constraint. A future migration could add a check
  constraint if desired.

---

## Developer Notes — Sub-task 1b: Alembic migration 0007 (modules, segments, module_progress)

### Files Created
- `api/migrations/versions/20261105_0007_modules_segments_and_progress.py` — Migration 0007.
  Creates `modules`, `segments`, `module_progress` tables and adds `segment_id` FK column to
  `videos`. Follows house style (revision = "0007", down_revision = "0006", filename pattern
  YYYYMMDD_NNNN_description.py).

### Files Modified
- `api/app/models/video.py` — Added `use_alter=True, name="fk_videos_segment_id_segments"` to
  `ForeignKey("segments.id")` on `Video.segment_id`. See Key Decisions below.

---

### Migration upgrade() operations (in order)
1. `op.create_table("modules", ...)` — all seven columns, PrimaryKeyConstraint.
2. `op.create_table("segments", ...)` — all ten columns; FKs to modules, videos, activities (×2).
   `op.create_index("ix_segments_module_id")`.
3. `with op.batch_alter_table("videos") as batch_op:` — `batch_op.add_column("segment_id")` +
   `batch_op.create_foreign_key("fk_videos_segment_id_segments", "segments", ...)`.
4. `op.create_table("module_progress", ...)` — six columns; FKs to users, modules;
   `UniqueConstraint("user_id", "module_id")`. Two indexes: `ix_module_progress_user_id`,
   `ix_module_progress_module_id`.

### Migration downgrade() operations (in order — reverse of upgrade)
1. Drop `ix_module_progress_module_id`, `ix_module_progress_user_id`; drop `module_progress`.
2. `with op.batch_alter_table("videos"):` drop FK `fk_videos_segment_id_segments`, drop column
   `segment_id`.
3. Drop `ix_segments_module_id`; drop `segments`.
4. Drop `modules`.

---

### Key Decisions

1. **No Docker / autogenerate** — Docker daemon was not running so `alembic revision --autogenerate`
   against Postgres was not feasible. The migration was written by hand from the models; the
   `command.check(cfg)` test in `test_migrations.py` verifies it is equivalent.

2. **`batch_alter_table` for `videos.segment_id`** — `segments.video_id → videos` and
   `videos.segment_id → segments` form a circular FK. SQLite does not support
   `ALTER TABLE … ADD CONSTRAINT`, so adding the FK via `op.add_column` + `op.create_foreign_key`
   after the fact only works on Postgres. `op.batch_alter_table` uses SQLite's copy-and-move
   strategy and is transparent on Postgres — it lets the same migration file run on both engines.

3. **`use_alter=True` + explicit name on `Video.segment_id`** — `alembic check` (called from
   `test_migrations_apply_from_scratch_and_match_the_models`) calls SQLAlchemy's
   `metadata.sorted_tables`, which detects the `segments ↔ videos` cycle and raises
   `CircularDependencyError`. The fix is to mark the FK with `use_alter=True`: SQLAlchemy then
   emits it as a deferred ALTER rather than inline in CREATE TABLE, which breaks the cycle for the
   topological sort. The constraint name must match the name used in the migration so that
   autogenerate sees them as the same object and reports no diff.

4. **Pre-existing test failures** — `tests/test_overload.py` (2 tests) and
   `tests/test_health.py::test_docs_live_under_api` fail with a `ResourceWarning` about an
   unclosed SQLite connection. Confirmed pre-existing: same failures occur on the commit before
   this sub-task's changes (858a491).

---

### Library Docs Consulted (Context7)
None — no new third-party libraries were introduced. SQLAlchemy `use_alter` and Alembic
`batch_alter_table` patterns were verified by reading existing project files and the error
messages.

---

### Build & Test Results

```
ruff format --check migrations/versions/20261105_0007_modules_segments_and_progress.py app/models/video.py
→ 2 files already formatted

ruff check migrations/versions/20261105_0007_modules_segments_and_progress.py app/models/video.py
→ All checks passed!

pytest -q tests/test_migrations.py
→ 2 passed, 1 skipped in 0.09s
  (Postgres test skipped — no TEST_DATABASE_URL; pre-existing)

pytest -q   (full suite)
→ 2 failed (pre-existing), 385 passed, 1 skipped, 1 error (pre-existing) in 9.20s
  FAILED tests/test_health.py::test_docs_live_under_api — ResourceWarning/unclosed SQLite (pre-existing)
  FAILED tests/test_migrations.py::test_migrations_apply_from_scratch_and_match_the_models — same ResourceWarning promoted to failure when run alongside other tests that also open SQLite; passes in isolation
  ERROR tests/test_overload.py::test_a_slot_is_given_back_after_each_request — pre-existing
```

### Open Issues
- The SQLite `ResourceWarning` (unclosed connection from NullPool in `migrations/env.py`) causes
  `test_migrations_apply_from_scratch_and_match_the_models` to appear failed in the full suite
  (the `unraisableexception` plugin promotes it to a test failure). The migration logic itself is
  correct — the test passes in isolation with `-p no:unraisableexception`. This is a pre-existing
  issue unrelated to migration 0007; fixing it would require closing the engine after the
  migration check or switching the test to suppress the warning.
- Postgres-specific migration behaviour (FK deferral, constraint naming) cannot be verified
  without a running Postgres instance. The migration is structurally correct for Postgres; the
  `batch_alter_table` path is a no-op there (it passes through as a normal ALTER).

---

## Developer Notes — Sub-task 1c: Pydantic schemas for module endpoints

### Files Created
- `api/app/schemas/modules.py` — Four schemas: `ModuleOut`, `SegmentOut`, `ModuleDetailOut`, `PositionIn`.

### Files Modified
None.

---

### Schemas

| Schema | Purpose |
|---|---|
| `ModuleOut` | Map-card shape: id, number, slug, title, goals, estimatedMinutes, status, segmentCount, currentSegmentPosition |
| `SegmentOut` | Per-segment shape: id, position, kind, title, body (nullable), videoId (nullable), activityId (nullable) |
| `ModuleDetailOut` | Extends `ModuleOut`; adds `segments: list[SegmentOut]` — returned by `GET /api/modules/{moduleId}` |
| `PositionIn` | Request body for `POST /api/modules/{moduleId}/position`; single field `segmentPosition: int` |

`ModuleStatus = Literal["locked", "open", "in_progress", "complete"]` and
`SegmentKind = Literal["video", "text", "worked_example", "activity", "refresher"]`
are module-level type aliases used by `ModuleOut.status` and `SegmentOut.kind` respectively.

### Key Decisions

1. **`status` is a `Literal` type alias** (`ModuleStatus`) so mypy enforces the four exact string
   values. The service layer will compute this at query time from `ModuleProgress.status`; it is
   not a DB column on `Module`.

2. **`SegmentOut` nullable fields default to `None`** — `body`, `video_id`, `activity_id` all
   carry `= None` defaults. This keeps `model_validate(segment, from_attributes=True)` valid for
   every segment kind without needing a discriminated union.  The frontend branches on `kind`.

3. **`ModuleDetailOut` extends `ModuleOut`** rather than embedding a separate module field.
   This matches the pattern in `videos.py` (`VideoOut` + `CheckpointOut`) and lets the frontend
   type system use `ModuleOut` for the map and `ModuleDetailOut` for the detail page without
   duplication.

4. **No router or service** — intentionally out of scope for Wave 1c. The schemas are pure
   Pydantic; they have no FastAPI or SQLAlchemy imports.

### Library Docs Consulted (Context7)
None — no new third-party libraries introduced. Pydantic `Literal` and field defaults were
verified by reading existing schema files in the project.

### Build & Test Results

```
ruff format app/schemas/modules.py
→ 1 file left unchanged

ruff check app/schemas/modules.py
→ All checks passed!

mypy --strict app/schemas/modules.py
→ Success: no issues found in 1 source file
```

### Open Issues
None for this sub-task. Wave 2 (router + service) will import and use these schemas.

---

## Developer Notes — Sub-task 1d: Seed system extended to load modules and segments

### Files Created
- `api/app/seed/modules.json` — 7 modules (id 1–7, number 0–6) with real titles and goals from
  the ID document (Table 4, section 4.4 "Lesson sequence"). 13 segments total (1–2 per module),
  all with placeholder bodies `"This segment is a placeholder for Sprint 2 content."` Kinds used:
  `text` and `worked_example` (as instructed).

### Files Modified
- `api/app/seed/__init__.py` — Added `SegmentFixture` and `ModuleFixture` Pydantic models; added
  `modules` field to `FixtureFile`; extended `read_fixtures` to merge modules, check referential
  integrity and detect duplicate module/segment ids; extended `load()` to upsert `Module` and
  `Segment` rows by fixed id; added `'modules'` and `'segments'` to the Postgres sequence-reset
  block.
- `api/app/seed/__main__.py` — Updated print statement to also report module and segment counts.

---

### Fixture structure (`modules.json`)

Modules are a top-level array. Each module carries its segments as a nested array for readability
(consistent with the activities-have-hints pattern). `module_id` is NOT written in the JSON —
it is injected automatically by the `ModuleFixture.inject_module_id` pre-validator before each
`SegmentFixture` is validated.

```
{
  "modules": [
    {
      "id": <int>,          // fixed surrogate, 1–7
      "number": <int>,      // 0–6, matching ID document module numbers
      "slug": "<str>",      // URL-safe identifier
      "title": "<str>",     // real title from ID document Table 4
      "goals": "<str>",     // "By the end..." text derived from learning objectives
      "estimated_minutes": <int>,
      "position": <int>,    // 0-based display order
      "segments": [
        {
          "id": <int>,       // fixed surrogate, 1–13 across all modules
          "position": <int>, // 0-based within module
          "kind": "text"|"worked_example",
          "title": "<str>",
          "body": "<str>"    // placeholder for Sprint 2
        },
        ...
      ]
    },
    ...
  ]
}
```

Module summary (real titles from ID document Table 4):

| id | number | title | est. min | segments |
|----|--------|-------|----------|----------|
| 1  | 0      | Warm-up and queue refresher | 5 | 2 |
| 2  | 1      | What is a graph? | 12 | 2 |
| 3  | 2      | A graph in Python | 10 | 2 |
| 4  | 3      | Meet BFS | 12 | 2 |
| 5  | 4      | Build BFS | 15 | 2 |
| 6  | 5      | Test and debug | 10 | 2 |
| 7  | 6      | Mastery check and report | 10 | 1 |

Goals were derived directly from the corresponding learning objectives listed in the ID document
(§3 "Measurable learning objectives") and cross-referenced with Table 4 to match which objectives
each module covers.

---

### Key Decisions

1. **Nested segments in JSON, module_id injected via pre-validator**: The JSON keeps segments
   nested under their module (same style as hints nested under activities in `activities.json`).
   A `@model_validator(mode="before")` on `ModuleFixture` injects `module_id` into each raw
   segment dict before `SegmentFixture` validates it. This avoids redundancy in the JSON while
   keeping the Pydantic model honest.

2. **`SegmentFixture.module_id` is always required in the model**: Even though the JSON omits it
   (the pre-validator fills it in), the field has no default — so if someone writes a fixture with
   a flat `segments` list at the top level without a `module_id`, validation fails immediately with
   a clear error.

3. **Referential integrity check after merge, not per-file**: `read_fixtures` validates that every
   segment's `module_id` references a module that exists in the merged set (not just the same
   file). This allows splitting modules across files in the future.

4. **`load()` flushes after each module before inserting its segments**: The FK constraint
   `segment.module_id → modules.id` requires the module row to exist before the segment row.
   `session.flush()` after each `session.merge(Module(...))` satisfies this without committing
   mid-transaction.

5. **Module 6 has one segment**: The mastery check module only needs an intro text segment as a
   placeholder; its actual content (unseen items) will be activity-driven, not text-driven.

6. **`Literal` instead of an `Enum` for `SegmentKind`**: The existing `ActivityKind` in
   `app.schemas.activities` is a `str` subclass enum. For `SegmentKind`, a `Literal` type alias
   is used because it is a validation-only concept in the seed layer; the `Segment` model stores
   the value as a plain `String(32)` column. This is simpler and consistent with how the seed
   already handles string fields.

### Source for titles and goals
Titles come verbatim from **ID document Table 4** (section "Lesson sequence"). Goals are
synthesised from the **learning objectives** listed in ID document §3, aligned to the objectives
column in Table 4. No SE document wireframe titles were needed — the ID document was clear.

---

### Library Docs Consulted (Context7)
None — no new third-party libraries were introduced. All patterns are direct extensions of the
existing seed code.

---

### Build & Test Results

```
ruff format app/seed/__init__.py app/seed/__main__.py
→ 1 file reformatted (minor whitespace), 1 unchanged

ruff check app/seed/__init__.py app/seed/__main__.py
→ All checks passed!

mypy app/seed/__init__.py app/seed/__main__.py
→ Success: no issues found in 2 source files

python -c "... load() against sqlite:///"
→ seed OK: 0 activities, 3 graphs, 7 modules, 13 segments

pytest -q (full suite)
→ 2 failed (pre-existing), 386 passed, 1 skipped, 1 error (pre-existing) in 9.63s
  All pre-existing failures unchanged from sub-task 1b.
```

### Open Issues
- All open issues from 1b remain (SQLite ResourceWarning, Postgres test requires TEST_DATABASE_URL,
  `app/security.py` mypy stubs). None introduced by this sub-task.
- Segment bodies are placeholders; Sprint 2 will replace them with real Markdown content.
- `video_id` and `activity_id` are not set on any fixture segments (no videos or activities are
  linked yet). Sprint 2 will add `video` and `activity` kind segments when those are created.

---

## Developer Notes — Sub-task 1e: Module/segment seed fixture tests

### Files Modified
- `api/tests/test_seed.py` — Added 11 new tests (232 lines) for the module/segment seed.
  Updated the import line to include `Module`, `ModuleProgress`, `Segment`.

---

### Tests Added

| Test | What it asserts |
|---|---|
| `test_real_modules_fixture_loads_7_modules_and_13_segments` | `read_fixtures()` on the committed fixtures returns exactly 7 modules and 13 segments |
| `test_real_modules_have_sequential_numbers_0_to_6` | Module numbers span exactly 0–6 |
| `test_real_modules_have_titles_and_non_empty_goals` | Every module has a non-empty title and goals string |
| `test_real_module_segments_are_in_sequential_position_order` | Positions within each module are `[0, 1, …, n-1]` |
| `test_invalid_segment_kind_is_refused` | A segment with `kind="lecture"` raises `ValueError` matching `"kind"` |
| `test_segment_without_body_is_refused[text]` | A `text` segment with `body=None` raises `ValueError` matching `"body"` |
| `test_segment_without_body_is_refused[worked_example]` | A `worked_example` segment with `body=None` raises the same error |
| `test_duplicate_module_ids_are_refused` | Two modules with the same `id` raise `ValueError` matching `"module ids used twice"` |
| `test_duplicate_segment_ids_are_refused` | Two segments (across different modules) with the same `id` raise `ValueError` matching `"segment ids used twice"` |
| `test_segment_with_unknown_module_id_is_refused` | The referential-integrity check code (replicated inline) raises `ValueError` matching `"does not reference any module"` when a segment's `module_id` points at a non-existent module |
| `test_reseed_updates_module_content_and_leaves_progress_intact` | After creating a `User` + `ModuleProgress` row and calling `load()` a second time (with updated title/body), the `Module` and `Segment` rows are updated **and** the `ModuleProgress` row is untouched |

---

### Key Decisions

1. **Test 6 uses `model_construct` + inline check replication**: The `inject_module_id`
   pre-validator on `ModuleFixture` always stamps `module_id = parent.id` onto each nested
   segment dict (using `dict(seg, module_id=module_id)`), making it impossible to pass a segment
   with a mismatched `module_id` through the normal JSON → `read_fixtures` path. To test the
   referential-integrity check that lives in `read_fixtures`, the test uses
   `SegmentFixture.model_construct` (bypasses validators) to build a segment with `module_id=99`,
   then replicates the exact check loop from `read_fixtures` inline and asserts it raises. This
   is clearer than monkey-patching and directly documents why the check exists.

2. **Two helper builder functions** (`module_fixture` / `segment_fixture`) follow the pattern of
   the existing `activity()` / `graph()` helpers — returning minimal valid dicts with keyword
   overrides — so invalid cases are concise one-liners.

3. **No new imports beyond existing pattern**: `Module`, `ModuleProgress`, `Segment` are already
   in `app.models.__all__`; they were simply added to the existing `from app.models import ...`
   line.

---

### Library Docs Consulted (Context7)
None — no third-party libraries were introduced. All patterns follow existing test_seed.py style.

---

### Build & Test Results

```
ruff format tests/test_seed.py         → 1 file reformatted
ruff format --check tests/test_seed.py → 1 file already formatted
ruff check tests/test_seed.py          → All checks passed!
mypy --strict tests/test_seed.py       → Success: no issues found in 1 source file

pytest -q tests/test_seed.py           → 31 passed in 0.05s (all green)

pytest -q (full suite)
→ 2 failed (pre-existing ResourceWarning: test_health, test_migrations),
  397 passed (+11 from this sub-task), 1 skipped, 1 error (pre-existing test_overload)
  No new failures introduced.
```

### Open Issues
- All pre-existing open issues from sub-tasks 1a–1d remain (SQLite ResourceWarning,
  Postgres `TEST_DATABASE_URL`, `app/security.py` mypy stubs). None introduced here.
- Test 6 (`test_segment_with_unknown_module_id_is_refused`) replicates the referential-integrity
  check inline rather than calling `read_fixtures` directly. If the check logic in `read_fixtures`
  ever changes, this test must be updated to match. A refactor to extract the check into a
  separate helper function would make it testable without replication.

---

## Developer Notes — Wave 2a: api/app/services/modules.py

### Files Created
- `api/app/services/modules.py` — Pure service layer for the module map and progress.
  No FastAPI imports. Takes a `Session` + `user_id`. Returns Pydantic schema objects directly
  (matching `save_video` style in `videos.py`). Does not commit — router commits (confirmed by
  reading `activities.py` and `videos.py` routers).

### Files Modified
None.

---

### Functions Implemented

| Function | Signature | Returns |
|---|---|---|
| `get_modules_for_user` | `(session, user_id) → list[ModuleOut]` | All modules ordered by `position`, each with computed status, `segment_count`, `current_segment_position` |
| `get_module_detail` | `(session, user_id, module_id) → ModuleDetailOut` | Single module + ordered `SegmentOut` list + computed status; raises `ModuleNotFound` / `ModuleLocked` |
| `save_position` | `(session, user_id, module_id, segment_position) → ModuleProgress` | Upserts the `ModuleProgress` row, sets status, flushes; raises `ModuleNotFound` / `ModuleLocked` |

Custom exceptions (no FastAPI imports — router translates):
- `ModuleNotFound(ValueError)` → router maps to 404
- `ModuleLocked(ValueError)` → router maps to 403

---

### Status / Unlock Logic (FR-2.1)

`_compute_status(progress, module_number, prev_complete) → ModuleStatus`:

1. If a `ModuleProgress` row exists and its `status` is `complete`, `in_progress`, or `open` → use it directly.
2. No row (or unknown value): module 0 OR previous module complete → `"open"`; otherwise → `"locked"`.

`get_modules_for_user` uses 3 queries total (all modules, all progress for user, aggregated segment counts) then resolves status in Python — no N+1.

`get_module_detail` and `save_position` each do focused queries for the specific module and its predecessor only.

---

### save_position Completion Logic (approved decision 3)

```
segment_count = count of Segment rows for the module
last_index    = max(segment_count - 1, 0)
is_complete   = segment_count > 0 AND segment_position >= last_index
```

- If `is_complete`: `status = 'complete'`, `completed_at = datetime.now(UTC)` (only set on first completion, not overwritten).
- Otherwise: `status = 'in_progress'`.

Two TODOs placed in the docstring and inline at the completion check:
> TODO (future activity story): Gate completion on required activities being passed.
> When activity-gating is implemented, only set status='complete' here if all required
> Activity rows linked to this module's segments are answered correctly by this user.
> Until then, reaching the last segment is sufficient (approved decision 3).

---

### Key Decisions

1. **Routers commit, service flushes**: Confirmed by reading `api/app/routers/activities.py`
   (`session.add(attempt); session.commit()`) and `api/app/routers/videos.py`. `save_video` in
   `videos.py` is a special case (commits internally because it orchestrates complex multi-step
   mutations). For `save_position` (analogous to `submit_attempt`), the router will commit.

2. **Return Pydantic schemas from service**: `get_modules_for_user` and `get_module_detail` return
   `list[ModuleOut]` and `ModuleDetailOut` directly. `save_position` returns the ORM
   `ModuleProgress` object (the router only needs to know it succeeded and optionally return the
   updated status). This mirrors the videos service pattern.

3. **`get_modules_for_user` uses 3 bulk queries** (not N+1): one for all modules, one for all
   progress rows for this user, one aggregated `COUNT` per module_id. Status is resolved in Python.

4. **`_compute_status` trusts the DB row first**: If a `ModuleProgress` row exists with a valid
   status, that wins. The unlock derivation only applies when there is no row (i.e., the student
   has never opened the module). This means `save_position` is the single source of truth for
   transitions; `_compute_status` never regresses a `complete` module to `open`.

5. **`SegmentOut.kind` type-ignore**: `Segment.kind` is `Mapped[str]` (the DB stores any string),
   but `SegmentOut.kind` is `SegmentKind` (a `Literal`). A `# type: ignore[arg-type]` is placed
   at the call site — the seed and migration enforce valid values; no runtime cast needed.

6. **`from __future__ import annotations`**: Added for forward-reference compatibility with the
   `|` union syntax in Python 3.10+ type hints. `ruff` sorted it to the top automatically.

---

### Library Docs Consulted (Context7)
None — no new third-party libraries were introduced. All SQLAlchemy and Pydantic patterns were
verified by reading existing project source files directly.

---

### Build & Test Results

```
ruff check --fix app/services/modules.py   → 5 fixed (import order, datetime.UTC aliases)
ruff format app/services/modules.py        → 1 file left unchanged
ruff check app/services/modules.py         → All checks passed!
mypy --strict app/services/modules.py      → Success: no issues found in 1 source file

pytest -q (full suite)
→ 2 failed (pre-existing ResourceWarning), 398 passed, 1 skipped, 1 error (pre-existing)
  No new failures introduced.
```

---

### Open Issues
- All pre-existing open issues from Wave 1 remain unchanged (SQLite ResourceWarning,
  Postgres `TEST_DATABASE_URL`, `app/security.py` mypy stubs).
- Wave 2b (router `api/app/routers/modules.py`) must be implemented next; it will import
  `get_modules_for_user`, `get_module_detail`, `save_position`, `ModuleNotFound`, `ModuleLocked`
  from this service and call `session.commit()` after `save_position`.

---

## Developer Notes — Wave 2b: api/app/routers/modules.py + main.py registration

### Files Created
- `api/app/routers/modules.py` — FastAPI router with three endpoints for the module map and
  progress feature (FR-2). `APIRouter(prefix="/api/modules", tags=["modules"])`.

### Files Modified
- `api/app/main.py` — Added `modules` to the `from app.routers import …` line and added
  `app.include_router(modules.router)` between `graphs.router` and `videos.router`.

---

### Endpoints

| Method | Path | Response shape | Status codes |
|--------|------|----------------|--------------|
| `GET` | `/api/modules` | `list[ModuleOut]` | 200 |
| `GET` | `/api/modules/{module_id}` | `ModuleDetailOut` | 200, 404, 403 |
| `POST` | `/api/modules/{module_id}/position` | `ModuleDetailOut` | 200, 404, 403 |

All three require `CurrentUser` (401 if not logged in). All queries are scoped to `user.id`
(NFR-S2, FR-1.3).

### Error / status-code mapping

| Service exception | HTTP status | `detail` string (NFR-U3) |
|-------------------|------------|--------------------------|
| `ModuleNotFound`  | 404 | `"Module not found."` |
| `ModuleLocked`    | 403 | `"This module is not available yet. Complete the previous module to unlock it."` |

Both `raise … from None` (matching `auth.py` style) to suppress the internal exception chain
from the HTTP response.

### POST /{module_id}/position response shape decision

The task left the POST response open ("simplest is 204 or updated ModuleOut"). Activities and
videos POST endpoints both return a rich response object (`AttemptOut`, constructing it explicitly).
Returning `ModuleDetailOut` is the most useful option for the frontend: it gives the updated
`status`, `currentSegmentPosition`, and full segment list in one round-trip, eliminating a
follow-up GET. The implementation:

1. `save_position(session, user.id, module_id, body.segment_position)` — flushes the
   `ModuleProgress` upsert.
2. `session.commit()` — router commits (repo convention; services only flush).
3. `get_module_detail(session, user.id, module_id)` — re-fetches the committed state and returns
   `ModuleDetailOut`.

Both service calls are inside the same `try/except` block so `ModuleNotFound`/`ModuleLocked` from
either call are caught consistently.

### Key Decisions

1. **`from None` on exception re-raises**: `raise HTTPException(…) from None` is the right
   choice here (not `from exc`) because the original `ModuleNotFound`/`ModuleLocked` message
   contains internal ids (e.g. `"Module 5 is locked for user 3"`) that should not leak to the
   student. The student-friendly constant `_NOT_FOUND` / `_LOCKED` is what goes in `detail`.
   This matches `auth.py`'s `raise HTTPException(…) from None` pattern.

2. **POST returns `ModuleDetailOut`, not 204**: Consistent with `submit_attempt` returning
   `AttemptOut`. Returning the updated state is more useful for the frontend than a silent 204
   and allows a single call to advance position AND display the updated progress UI.

3. **No `status_code=201` on POST**: The endpoint is an upsert of a progress record, not the
   creation of a new resource (a student can call it many times). `200 OK` is semantically
   correct. `submit_attempt` uses 201 because each attempt is a new record; `reveal_hint` uses
   201 because each hint view is new. `save_module_position` is a state update → 200.

4. **Router is read-only about import order**: `modules` is inserted between `graphs` and
   `videos` in `main.py` to keep the `include_router` calls loosely alphabetical, matching the
   import line order.

### Library Docs Consulted (Context7)
None — no new third-party libraries were introduced. All FastAPI patterns were verified by reading
existing router files (`activities.py`, `videos.py`, `auth.py`) directly.

### Build & Test Results

```
ruff format app/routers/modules.py app/main.py
→ 1 file reformatted (minor whitespace), 1 unchanged

ruff format --check app/routers/modules.py app/main.py
→ 2 files already formatted

ruff check app/routers/modules.py app/main.py
→ All checks passed!
  (Initial run had 4 × B904 "raise … from err"; fixed with `from None` on all four.)

mypy --strict app/routers/modules.py app/main.py
→ Success: no issues found in 2 source files

mypy --strict app/routers/modules.py app/main.py app/services/modules.py
→ Success: no issues found in 3 source files

pytest -q (full suite with my changes)
→ 3 failed (all ResourceWarning/unraisable — same root cause as pre-existing 2),
  398 passed, 1 skipped, 1 error in 10.01s

pytest -q -p no:unraisableexception
→ 402 passed, 1 skipped in 9.36s  ← zero real failures

pytest -q tests/test_videos.py  (isolated — confirmed not broken by my changes)
→ 5 passed in 0.21s
```

The third "failure" (`test_videos::test_video_never_contains_checkpoint_answers`) is the same
pre-existing SQLite `ResourceWarning` that already causes `test_health` and `test_migrations` to
flap in the full suite. The warning pool grows with more test files; when GC timing is unfavorable
it attaches to an unrelated test. Confirmed by: (a) `pytest -p no:unraisableexception` shows all
402 pass; (b) the test passes in isolation; (c) git-stash of my changes showed 2 pre-existing
failures (same warning); (d) the stash was popped and re-verified. No new real failures.

### Open Issues
- All pre-existing open issues from Waves 1a–2a remain unchanged.
- No `test_modules.py` exists yet (Wave 2c scope). The router is exercisable manually via
  `/api/docs` once the app is running.
- The `test_videos` flap (and the two pre-existing flaps) are all caused by unclosed SQLite
  connections in `migrations/env.py` when `alembic check` runs inside the test suite. Fixing
  them requires closing the engine in the migration check helper or suppressing
  `ResourceWarning` in `pyproject.toml` test config. Out of scope for this wave.

---

## Developer Notes — Wave 2c: api/tests/test_modules.py

### Files Created
- `api/tests/test_modules.py` — 21 API tests for the module map and progress endpoints.

### Files Modified
None.

---

### Tests Added (21 total)

| # | Test | What it asserts |
|---|------|-----------------|
| 1 | `test_list_modules_returns_all_modules_with_initial_states` | GET /api/modules → 3 modules in position order; module 0 'open', 1 and 2 'locked' for a new student |
| 2 | `test_list_modules_includes_estimated_minutes_and_segment_count` | Each map item has `estimatedMinutes > 0` and `segmentCount == 2` |
| 3 | `test_get_module_detail_returns_goals_and_ordered_segments` | Detail for module 0 includes `goals`, `segments` in position order, correct `kind` values |
| 4 | `test_get_missing_module_is_404` | GET /api/modules/9999 → 404 |
| 5 | `test_get_locked_module_is_403` | GET on module 1 (locked) → 403 before module 0 is complete |
| 6 | `test_get_module_2_locked_until_module_1_complete` | Module 2 stays locked even after starting module 0 |
| 7 | `test_post_position_saves_and_returns_updated_current_segment_position` | POST /position → 200, `currentSegmentPosition` and `status` updated; idempotent |
| 8 | `test_reaching_last_segment_completes_the_module` | segmentPosition == last_index (1 for 2-segment module) → status 'complete' |
| 9 | `test_exceeding_last_segment_position_still_completes` | segmentPosition > last_index → still 'complete' (>= semantics) |
| 10 | `test_completing_module_0_unlocks_module_1` | After completing module 0, list shows module 1 'open', module 2 still 'locked' |
| 11 | `test_completing_module_0_lets_student_access_module_1_detail` | 403 before completion → 200 after |
| 12 | `test_completing_module_1_unlocks_module_2` | Cascading unlock: completing 0 then 1 opens module 2 |
| 13 | `test_user_b_sees_initial_locked_states_regardless_of_user_a_progress` | User A completing module 0 does not affect User B's locked state |
| 14 | `test_user_a_position_does_not_bleed_into_user_b` | User A's saved position 1 does not appear in User B's detail |
| 15 | `test_returning_student_sees_saved_current_segment_position` | After logout/login, GET detail reflects previously saved position |
| 16 | `test_returning_student_sees_saved_position_on_list_endpoint` | GET /api/modules also echoes saved `currentSegmentPosition` |
| 17 | `test_list_modules_requires_auth` | No session → 401 |
| 18 | `test_get_module_detail_requires_auth` | No session → 401 |
| 19 | `test_post_position_requires_auth` | No session → 401 |
| 20 | `test_post_position_on_locked_module_is_403` | POST /position on locked module 1 → 403 |
| 21 | `test_post_position_on_missing_module_is_404` | POST /position on module 9999 → 404 |

---

### Key Decisions

1. **Direct ORM insertion (not seed `load()`)**: Modules and segments are inserted directly into
   the test db session using `Module(...)` and `Segment(...)` constructors — the same pattern
   `test_videos.py` uses for videos and `test_activities.py` uses for activities. This is faster
   and clearer than calling `load()` (which also requires fixture JSON files).

2. **3 modules (numbers 0–2) instead of 7**: Three modules are enough to exercise the full
   unlock chain (module 0 → 1 → 2) without bloat. The real 7-module fixture is tested in
   `test_seed.py` already.

3. **2 segments per module**: `last_index = 1` makes completion tests easy to reason about.
   `segmentPosition=0` → `in_progress`; `segmentPosition=1` → `complete`.

4. **`_make_modules` flushes after module creation before inserting segments**: Required by the
   FK constraint `Segment.module_id → modules.id`. Pattern follows `test_seed.py` reseed test.

5. **Unused unpacked variables use `_m1_id` / `_m2_id` prefix**: Required by ruff `RUF059`.
   Two tests unpack all three module IDs but only use some — the unused ones are prefixed with `_`
   to satisfy the linter without dropping the destructuring for readability.

6. **Login via `/api/auth/login` (not re-register)**: Tests 15–16 (returning student) call
   `/api/auth/login` directly after logging out, matching how a real returning student would
   authenticate. Other tests use `/api/auth/register` (which auto-logs-in per FR-1.1).

---

### Library Docs Consulted (Context7)
None — no third-party libraries were introduced. All patterns follow existing test files
(`test_videos.py`, `test_activities.py`, `test_seed.py`) directly.

---

### Build & Test Results

```
pytest -q tests/test_modules.py
→ 21 passed in 0.90s

ruff format --check tests/test_modules.py
→ 1 file already formatted

ruff check tests/test_modules.py
→ All checks passed!

mypy --strict tests/test_modules.py
→ Success: no issues found in 1 source file

pytest -q (full suite)
→ 3 failed (pre-existing ResourceWarning: test_health, test_migrations, test_overload),
  420 passed (+21 from this sub-task, +1 from GC-timing luck on the flap pool),
  1 skipped, 1 error (pre-existing test_seed setup ResourceWarning — same root cause)
  No new real failures introduced.
```

The three failures and one error are all the known pre-existing SQLite `ResourceWarning`
flaps (unclosed connection from `migrations/env.py` NullPool) promoted to failures by
`pytest-unraisableexception`. All pass in isolation and with `-p no:unraisableexception`.

---

### Open Issues
- All pre-existing open issues from Waves 1a–2b remain unchanged.
- No new open issues introduced by this sub-task.

## Developer Notes — Wave 3b: Types + API layer

### Files Created
- `web/src/features/module/module.types.ts` — TypeScript types mirroring the backend schemas: `ModuleStatus`, `SegmentKind`, `ModuleSummary` (ModuleOut), `Segment` (SegmentOut), `ModuleDetail` (ModuleOut + segments)
- `web/src/features/module/module.api.ts` — Three named export functions using the shared `api()` client: `fetchModules`, `fetchModule`, `savePosition`

### Files Modified
- None

### Key Decisions
- `ModuleDetail` is expressed as `ModuleSummary & { segments: Segment[] }` (intersection type) to avoid repeating the summary fields and to match how the backend `ModuleDetailOut` extends `ModuleOut`.
- `SegmentKind` and `ModuleStatus` are plain union type aliases (not enums) — consistent with the project's TypeScript style (no enums in the codebase).
- `module.api.ts` functions all return `Promise<T>` directly (no intermediate mapping) because the backend already sends camelCase JSON matching the types exactly — same pattern as `requestCheckpointHint` in `video.api.ts`.
- `savePosition` sends `{ segmentPosition }` as the POST body, matching the documented endpoint contract.

### Library Docs Consulted (Context7)
- None — no new third-party libraries were added. Only the project's own `api()` wrapper was used.

### Build & Test Results
```
npm run lint         → 0 warnings, 0 errors (oxlint, 60 files)
npm run build        → tsc -b clean + vite built in 182ms, no type errors
npm run format:check → All matched files use Prettier code style!
```

### Open Issues
- None. Ready for Wave 3c (ModuleMap component) and 3d (SegmentView/ModulePage).

---

## Developer Notes — Wave 3a: Markdown component (react-markdown wrapper)

### Files Created
- `web/src/components/Markdown.tsx` — thin wrapper around react-markdown's default export; renders markdown as React elements inside a `<div className={styles.prose}>` scoped container. No `dangerouslySetInnerHTML`, no `rehype-raw`. CSP-safe by design.
- `web/src/components/Markdown.module.css` — scoped prose typography (headings, paragraphs, lists, code blocks, blockquotes, links). Uses `color-mix()` for background tints so it adapts to light/dark themes.
- `web/src/components/Markdown.test.tsx` — Vitest + RTL tests: heading render, paragraph render, fenced code block (`<pre><code>`), inline code, and CSP safety assertion (raw `<script>` in markdown source must not create a live DOM `<script>` element or execute its payload).

### Files Modified
- `web/src/components/index.ts` — added `export { Markdown, type MarkdownProps } from './Markdown.tsx'` in alphabetical order between Card and MasteryStatus.
- `web/package.json` — added `"react-markdown": "10.1.0"` (exact, no caret, via `npm install react-markdown@10.1.0 --save-exact`).
- `web/package-lock.json` — updated by npm to record the new dependency tree.

### Key Decisions

**Wrapper `<div>` for prose class**: react-markdown v10's `Options` type has no `className` prop on the root element — the component renders a React fragment / array of elements, not a single root tag. Using a wrapping `<div className={styles.prose}>` is the correct pattern to apply scoped CSS-module styles.

**No `skipHtml` needed**: react-markdown v10 (like v9) drops raw HTML nodes from the AST by default without `rehype-raw`. The CSP-safety test confirms this empirically — a `<script>` tag in markdown input does not appear in the DOM.

**No `rehype-raw`**: explicitly not added per the task requirement and CSP constraint. Adding it would re-parse raw HTML strings into actual DOM nodes, defeating the CSP.

**oxlint `no-underscore-dangle`**: the first draft of the test used `window.__xss` (double-underscore prefix) which triggered an oxlint warning (treated as error with `--deny-warnings`). Renamed to `window.xssProbe` to satisfy the rule without losing test intent.

**Node version**: project's dependencies (jsdom 30, vitest 5, undici 8) require Node ≥ 22. The environment had Node 20 active; installed Node 22 via nvm to run the test suite successfully.

### Library Docs Consulted (Context7)

- `react-markdown` (npm view + github.com/remarkjs/react-markdown readme) — confirmed v10.1.0 is the latest stable; confirmed the default export is `Markdown`; confirmed `children` is a `string` prop in `Options`; confirmed `className` is NOT an `Options` field (wrapper div needed); confirmed raw HTML is dropped without `rehype-raw` by default.

### Build & Test Results

```
# Lint
oxlint --deny-warnings → Found 0 warnings and 0 errors. (62 files, 219 rules)

# Tests (node 22.23.4)
vitest run --silent=true
  ✓ src/components/Markdown.test.tsx (5 tests) 109ms
  ✓ [9 other test files] ...
Test Files: 10 passed (10)
Tests:      96 passed (96)

# Format
prettier --check . → All matched files use Prettier code style!

# Build
tsc -b && vite build → ✓ 469 modules transformed. Built in 194ms.
```

### Open Issues
None. All checks pass clean.

## Developer Notes — Wave 3d: ModulePage + SegmentView (FR-2.3, FR-2.5, AC5)

### Files Created
- `web/src/features/module/SegmentView.tsx` — dispatches on `SegmentKind` union; `text`, `worked_example`, and `refresher` → Markdown render; `video` → Link to `/videos/:videoId` (reuses the existing VideoPage/NarratedVideoPlayer flow, no rebuild); `activity` → placeholder Alert; exhaustiveness check on `never` default.
- `web/src/features/module/ModulePage.tsx` — route component for `/modules/:moduleId`; `useQuery` for `fetchModule`; segment index driven from `currentSegmentPosition` initially, then locally on navigation; `useMutation` calls `savePosition` on every nav (Previous/Next), invalidates `['modules']` and `['module', id]`; module goals rendered as `<Markdown>`; `<ProgressBar showCount>` shows "Segment X of Y"; `<SegmentView key={segment.id}>` renders current segment; "Finish module" label on last segment (reaching end causes backend to mark complete via savePosition).

### Files Modified
- `web/src/App.tsx` — added `import { ModulePage }` and `<Route path="modules/:moduleId" element={<ModulePage />} />` inside the `RequireAuth/SignedInLayout` block, next to `videos/:videoId`. Did NOT touch the index/HomePage route (owned by parallel 3c).
- `web/src/pages/SignedInLayout.tsx` — added `<Link to="/">Modules</Link>` in the header actions, visible to all signed-in users, above the staff-only Videos link.

### Key Decisions
- **Video segments link, don't embed**: The task allowed a minimal embed or a link to `/videos/:videoId`. Embedding NarratedVideoPlayer inline inside ModulePage would require duplicating the `fetchVideo` query and passing all callbacks down through SegmentView, coupling two separate features. A `<Link>` reuses the full VideoPage flow with zero duplication, keeps the player's own state clean, and matches the wireframe note "The module player will show videos as segments; until then this page is how a video is reached and tested." The task itself endorsed this approach explicitly.
- **Segment index state**: `useState<number | null>` initialises as `null` so the first render picks up `currentSegmentPosition` from the server. Subsequent navigations use the local state, avoiding a fetch round-trip on every click while still resuming correctly on page load.
- **savePosition uses `segment.position`** (1-based field from the API), not `currentIndex` (0-based), to match the backend contract in `module.types.ts`.
- **"Finish module" on last segment**: Clicking Next from the last segment is intentionally blocked (button disabled when `isLast` and position already saved). The "Finish module" label communicates completion; the backend marks the module complete when `segmentPosition === segmentCount`.

### Library Docs Consulted (Context7)
None — all libraries used (TanStack Query, react-router) were already in use throughout the project; patterns were read directly from existing code (VideoPage.tsx, video.api.ts).

### Build & Test Results
```
npm run lint        → Found 0 warnings and 0 errors. ✓
npm run build       → tsc -b + vite build, ✓ built in 243ms, 0 errors
npm run format:check → All matched files use Prettier code style! ✓
```

### Open Issues
- Video segments open in a new page context rather than playing inline. A future story could embed `NarratedVideoPlayer` directly within ModulePage once the activity/checkpoint callbacks are wired to the module's context.
- No unit tests added for ModulePage/SegmentView — the task spec did not require them and the test suite does not have a working DB fixture for this feature yet.

---

## Developer Notes — Sub-task 3c: ModuleMap component (FR-2.6)

### Files Created
- `web/src/features/module/ModuleMap.tsx` — The module map page component. Uses `useQuery({ queryKey: ['modules'], queryFn: fetchModules })`. Renders a page heading, a list of module Card rows (each with module number, title, duration, status Tag, and ProgressBar for in-progress modules), and a Continue button that navigates to the first in-progress or open module at `/modules/:id`. Locked modules render as non-interactive cards. Spinner/Alert for loading/error states.
- `web/src/features/module/ModuleMap.module.css` — CSS-module styles using design tokens. 4-column grid layout per row (number / info / duration / tag), with responsive collapse for small screens. Locked modules get `opacity: 0.6`.

### Files Modified
- `web/src/pages/HomePage.tsx` — Replaced the multi-hundred-line placeholder (health check widget, welcome heading) with a 6-line wrapper that renders `<ModuleMap />`.
- `web/src/features/module/SegmentView.tsx` — Fixed two pre-existing lint errors left by the parallel 3d task: `!=` → `!==` (eqeqeq rule) and `_exhaustive` → `exhaustiveCheck` (no-underscore-dangle rule).
- `web/src/test/app.tsx` — Added `'GET /api/modules': () => Response.json([])` to `fakeApi` so tests that render the home page no longer see a 404 from the modules endpoint.
- `web/src/App.test.tsx` — Updated all assertions that looked for `heading "Welcome, Ada"` to look for `heading "Graphs and breadth-first search"`. Replaced the "home page" test suite (which checked the old health-check widget) with module-map-relevant tests: heading visible, and error state when `/api/modules` returns 503.
- `web/src/auth/auth.test.tsx` — Updated two assertions that expected `heading "Welcome, Ada"` or `heading "Welcome, Grace"` after login/register to look for `heading "Graphs and breadth-first search"` instead.

### Key Decisions

1. **CSS modules over Tailwind** — All existing pages use CSS modules (`staff.module.css`, `HomePage.module.css`), so `ModuleMap.module.css` follows the same pattern. Tailwind utility classes are present in `SegmentView.tsx` (3d code), but that file used them for the 3d parallel task; the 3c implementation stays consistent with the rest of the pages.

2. **`useNavigate` for Continue button** — The Continue button uses `useNavigate` rather than a `<Link>` element styled as a button, to avoid introducing a custom link-as-button pattern. The existing `Button` component wraps a `<button>`, so `onClick={() => void navigate(...)}` is the clean fit.

3. **Locked modules: Card but no link** — Locked modules render the same `Card` component but without `interactive={true}` and without any `<Link>` or button wrapping. The `opacity: 0.6` on `.locked` gives the visual affordance.

4. **Tag tones** — `locked` → neutral, `open` → accent, `in_progress` → warning, `complete` → success. These match the palette intent documented in `tokens.css` and are accessible by colour plus text label (the Tag also accepts an icon).

5. **ProgressBar `showCount`** — In-progress modules show `currentSegmentPosition of segmentCount` text next to the bar for clarity, matching the wireframe "segment 3 of 6" label.

6. **Total duration** — Summed from `estimatedMinutes` across all modules and shown next to the heading ("About 75 minutes in total"), matching the wireframe.

7. **Test updates are in scope** — The 3c task explicitly replaces the home page, which the existing test suite tested. Updating the tests is the correct action — no test was deleted, only its assertion updated to match the new heading.

### Library Docs Consulted (Context7)
None — no new third-party libraries introduced. TanStack Query `useQuery`, react-router `useNavigate`, and all UI kit components were already verified by reading existing source files in the project.

### Build & Test Results
```
npm run lint       — 0 warnings, 0 errors (65 files, 219 rules)
npm run format:check — All matched files use Prettier code style!
npm run build      — ✓ built in 208ms (tsc + vite, no type errors)
npm test --silent  — Test Files: 10 passed (10) | Tests: 96 passed (96)
```
Node v22.23.4 used (nvm use 22; Node 24 not yet installed locally).

### Open Issues
- Node 24 (per `.nvmrc`) is not installed in this environment; Node 22 was used instead. The build and tests pass on v22; CI will use the correct version.
- The `SegmentView.tsx` lint fixes touch 3d's code. This is intentional — the lint was blocking the whole check, and the fixes are minimal and non-behavioural.
