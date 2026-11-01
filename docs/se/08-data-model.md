# Data Model

## Entities (conceptual)

**User**
- `id` (PK), `username`, `email` (**required** — account identity/recovery), `display_name` (**required** — shown on the leaderboard), `is_anonymous_on_leaderboard` (bool, default `false` — when `true`, the public leaderboard shows an anonymised label instead of `display_name`), `password_hash`, `created_at`.

**Lesson**
- `id` (PK), `topic` (e.g. "Graphs+BFS"), `title`, `description`, `order`.

**ContentItem** (multi-mode content)
- `id` (PK), `lesson_id` (FK→Lesson), `mode` (`video`|`text`|`interactive`), `title`, `body_ref` (text body or asset reference), `order`.

**Video** (specialisation of/linked to a `video` ContentItem)
- `id` (PK), `content_item_id` (FK→ContentItem), `media_url`, `duration_seconds`.

**VideoCheckpoint**
- `id` (PK), `video_id` (FK→Video), `timestamp_seconds`, `gate_policy` (Draft 1 value: `retry_until_correct` — student may retry; playback resumes only after a correct answer; no permanent lockout. Enum retained for future policies such as `submit`).

**Question**
- `id` (PK), `type` (`mcq`|`truefalse`|`short`) , `prompt`, `options` (JSON for choices), `correct_answer`/`answer_key` (JSON), `difficulty` **[PROVISIONAL]**, optional `checkpoint_id` (FK→VideoCheckpoint), optional `assessment_id` (FK→Assessment).

**ProgressEvent**
- `id` (PK), `user_id` (FK→User), `event_type` (`checkpoint_answer`|`lesson_complete`|`mode_viewed`|`assessment_submitted`), `ref_id` (polymorphic reference), `payload` (JSON), `created_at`.
- *Design note:* ProgressEvent is the append-only source of truth; `Score` is derived/aggregated from events. **Every** checkpoint attempt (correct and incorrect) is recorded as a `checkpoint_answer` event; the `payload` captures correctness and whether it was the first attempt vs a retry, which drives the first-attempt (10 pts) vs retry (5 pts) scoring rule.

**Score**
- `user_id` (FK→User, PK), `total_points`, `updated_at`. (Aggregate projection; may be recomputed from ProgressEvent.)

**Leaderboard**
- Not necessarily a stored table — Draft 1 may compute it as a query over `Score`/`ProgressEvent` (ranking). A materialised leaderboard table is **[PROVISIONAL]** if performance requires it.

**Assessment**
- `id` (PK), `lesson_id` (FK→Lesson), `title`, `pass_threshold` (the single global threshold used in Draft 1), `scaffold_rules` (JSON). *Draft 1 uses only the global pass/fail branch of `scaffold_rules`; the JSON shape is retained so per-concept weakness→scaffold mappings can be added in Draft 2 without a schema change.*

**AssessmentResult**
- `id` (PK), `user_id` (FK→User), `assessment_id` (FK→Assessment), `score`, `passed` (bool), `branch_taken` (`none`|`scaffold`), `answers` (JSON), `created_at`.

**GraphScenario** (BFS scenario)
- `id` (PK), `name`, `directed` (bool), `nodes` (JSON: list of node ids/labels), `edges` (JSON: list of `{source, target, weight?}`), `default_start_node`.

## Key relationships
- Lesson 1—* ContentItem; ContentItem 0..1—1 Video (for `video` mode).
- Video 1—* VideoCheckpoint; VideoCheckpoint 1—* Question.
- Assessment 1—* Question; Assessment 1—* AssessmentResult.
- User 1—* ProgressEvent; User 1—1 Score; User 1—* AssessmentResult.
- GraphScenario is standalone content consumed by the BFS feature (optionally linkable to a Lesson **[PROVISIONAL]**).

## Notes
- JSON columns are used for flexible/evolving shapes (options, answers, edges, scaffold rules) in Draft 1; some may be normalised into tables in later drafts.
- Scoring authority lives in ProgressEvent + server rules, never in client submissions.
