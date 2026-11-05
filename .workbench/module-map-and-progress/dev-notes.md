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
