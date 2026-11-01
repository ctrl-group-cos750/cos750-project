---
title: Software Engineering Document
short: SE document
version: Draft 2
---

# Overview & Purpose

> **Scope of this document:** Software engineering only. Instructional-design content (learning theories, learning styles, motivation, pedagogy) is deliberately excluded and lives in the separate ID document.

> **DRAFT 2.** Scope is intentionally open. Sections or decisions that are provisional and expected to change are tagged **[PROVISIONAL]**. Items requiring a decision are collected in §14.

## Purpose
The COS212 app is a pre-lecture, tutor-style learning application that teaches **one data structure (Graphs)** and **one algorithm (Breadth-First Search)**. It is used by a student **before** attending the corresponding lecture and assumes **zero prior knowledge** of the topic.

From an engineering standpoint, the system is a web application composed of:
- a **Python backend** that computes BFS traversals, serves content, manages user accounts, tracks scoring/progress, and exposes a REST API;
- a **TypeScript + React frontend** that renders interactive video, interactive graph visualizations, assessments, and a leaderboard;
- a **persistent data store** holding users, content, progress events, scores, and assessment results.

## Engineering goals
- Deterministic, inspectable BFS step generation suitable for front-end animation.
- Clear client/server separation over a documented REST API.
- Persistent user accounts and progress to support gamification (points + leaderboard).
- A content system that can deliver the same lesson concept in multiple modes (video, text, interactive) without code changes per lesson.
- An assessment subsystem whose branching (adaptive scaffolding) is driven by data/config rather than hard-coded logic where practical.

## Primary user & session shape
A single primary role for Draft 1: **Student**. A secondary **Content author/admin** role is noted but out of scope for Draft 1 (§3.2). A typical session: authenticate → work through a lesson (video + text + interactive) → answer embedded questions → step through a BFS visualization → take an assessment → receive scaffolding if needed → see points and leaderboard position.

# Software engineering approach

## Choice: Scrum with one-week sprints

We follow **Scrum**, an Agile methodology, with one-week sprints. Each sprint ends with a working
increment deployed to staging, where the whole team, including the instructional designers, reviews it.

The COS750 lifecycle lecture (L11) lists the methodologies we considered. We chose Scrum because of
four properties of this project:

1. **The requirements arrive while we build.** The ID team designs the content, the assessment and
   the scaffolding at the same time as we build the platform. A plan-driven model (Waterfall,
   V-model) needs stable requirements before design starts; Scrum expects them to change and
   reprioritises every sprint.
2. **The deadline is fixed and the scope is not.** The prototype must be demonstrated on
   16/17 November. Time-boxed sprints with a prioritised backlog mean that the most important
   features are finished first, and that something complete and working exists at the end of every
   week.
3. **An educational app has to be tried by learners.** Each sprint ends with a deployed increment
   we can put in front of students and the ID team, so feedback shapes the next sprint instead of
   arriving after the build.
4. **It fits the ID process.** The ID document uses ADDIE as a repeating cycle with rapid
   prototyping inside it, testing early versions of lessons with peers (ID document §4.1). Scrum
   gives those prototypes a fixed rhythm: each sprint's increment on staging is the version the ID
   team tests, and its sprint review is where their formative evaluation feeds back into our
   backlog. ADDIE's Develop and Implement phases run inside Sprints 1 and 2, and the pilot session
   with peers is a backlog item like any other.

**Methodologies we did not choose:**

| Methodology | Why not |
|---|---|
| Waterfall and V-model | They need fixed requirements up front, but ours depend on ID work still in progress. Testing comes last, which leaves no time to recover from what it finds before a fixed demo date. |
| Spiral | Its risk analysis each cycle is designed for large, long, high-risk projects. Too heavy for a two-week build. |
| Incremental (plan-driven) | We do deliver in increments, but planned per sprint, not all fixed at the start. |
| Prototyping | Each sprint review works like a prototype review, but on its own prototyping gives no roles, cadence or backlog to coordinate seven people. |
| XP | We use several XP practices: continuous integration, small releases, collective code ownership through PR review, and coding standards enforced by linters. We don't follow its full discipline of pair programming and test-first development with three engineers across different schedules. |

## Roles

| Role | Who | Responsibilities |
|---|---|---|
| Scrum Master | **[to be decided]** | Runs the events, removes blockers, keeps the board and the process honest, and facilitates backlog ordering. |
| Development team | Matthew Els, Ayanda Juqu, Reece Schmidt (software engineering); Joshua Wereley, Simphiwe Nhlapo, Mohtashim Hussain, Jacobus Hoogenboezem (content, assessment and scaffolding design) | Build the increment. ID members own content items on the same backlog. |

**No Product Owner.** Standard Scrum has a Product Owner who owns the backlog and accepts work. We
deliberately don't appoint one, because the product's requirements are fixed by sources outside the
team: the examination specification (from the COS212 lecturer, our client) and the ID document's
learning outcomes. The Product Owner's duties are shared instead:

- **Backlog order** is agreed by the whole team at sprint planning, facilitated by the Scrum Master.
  Items that cover the specification's hard requirement (an assessment that gives struggling
  students extra scaffolding) always come first.
- **Acceptance** is checked against each item's acceptance criteria at the sprint review. Content
  items are accepted by the ID members; platform items by an engineer other than the author.

## Timeline

| Sprint | Dates | Goal |
|---|---|---|
| Sprint 0 | 22 Oct – 1 Nov | Foundation. Spec issued 22 Oct, group registered 23 Oct, topic chosen (graphs + BFS), repository and branch flow, CI, hosting on staging and production, database layer with migrations, backups, staging login. |
| Sprint 1 | 2 – 8 Nov | **A complete path through the app.** A student can register, open a lesson, answer a checkpoint question in a video, step through BFS on a predefined graph, take the assessment and be sent to scaffolding when below the threshold, all with placeholder content, deployed to staging. |
| Sprint 2 | 9 – 15 Nov | **Real content and the full feature set.** The ID team's content, questions and scaffolds loaded; points and leaderboard; text, video and interactive modes; usability test with students; end-to-end tests; accessibility pass. |
| Release | 12 – 16 Nov | Feature freeze **Thu 12 Nov**. `staging` → `master` (production) **Fri 13 Nov**. Demo rehearsals on production 14–15 Nov. SE and ID documents submitted before **08:00 on Mon 16 Nov**. Presentation and demo on 16 or 17 Nov. |

## Artefacts

- **Product backlog:** a GitHub Project board linked to the repository. Each item is an issue
  written as a user story ("As a student with no graph knowledge, I want …, so that …"), with
  acceptance criteria and the requirement IDs it covers (FR-x.y, §6). ID work (videos, question
  banks, scaffold content) is on the same board with a `content` label, so dependencies between the
  two teams are visible.
- **Sprint backlog:** the items assigned to the current sprint's iteration on the board, with a
  sprint goal.
- **Increment:** whatever is deployed to staging.ctrlacademy.co.za at the end of the sprint.
- **Definition of Done.** An item is done only when:
  1. its acceptance criteria are met;
  2. it has tests (unit or API tests; an end-to-end test for user-facing flows);
  3. its PR is reviewed and approved by another engineer;
  4. CI passes (format, lint, types, tests, builds);
  5. it is merged into `staging`, deployed, and checked on staging.
- **Estimates:** story points on the Fibonacci scale (1, 2, 3, 5, 8), so the board's burn-up
  chart shows progress against each sprint's commitment.

## Events

| Event | When and how | Output |
|---|---|---|
| Daily stand-up | Asynchronous, a short message in the team's Discord stand-up channel every day: done since last time, doing next, blocked by. | Dated record of progress and blockers. |
| Sprint review | Weekly team call, first part. The increment is demonstrated on staging to the whole team, including the ID members; each item is accepted or rejected against its acceptance criteria. | Accepted items; feedback added to the backlog. |
| Retrospective | Same call, second part. What went well, what to change, one concrete action for next sprint. | Retro notes kept with the sprint (`docs/se/sprints/`). |
| Sprint planning | Same call, last part. Pick the sprint goal and the items from the top of the backlog that fit. | Sprint goal and sprint backlog on the board. |

The weekly call is on **[day and time to be agreed]**.

TODO: Choose the Scrum Master and the weekly call's day and time at the team meeting.

## Engineering practices that support the process

These are what make a working increment at the end of every week possible. Details are in §13.

- **Branching:** each backlog item gets a feature branch and a PR into `staging`; `staging` is
  promoted to `master` by PR. A CI check rejects PRs into `master` that don't come from `staging`.
- **Code review:** every PR is reviewed by another engineer before it is merged.
- **Continuous integration:** every PR runs formatting, linting, type checks, tests and builds
  for both apps and the Docker images.
- **Continuous delivery:** a merge into `staging` deploys to staging automatically; `master`
  deploys to production. Database migrations run on deploy.
- **Separate environments:** local, staging (behind a team password) and production, each with its
  own database.

## Evidence

| Claim | Where to see it |
|---|---|
| Backlog, sprints, estimates, burn-up | GitHub Project board **[link to be added]** |
| Daily stand-ups | Discord stand-up channel (exported for the appendix) |
| Reviews, retros and planning | `docs/se/sprints/` in the repository |
| Code review and Definition of Done | Merged PRs and their reviews on GitHub |
| CI and continuous delivery | GitHub Actions history; Coolify deployment log |

TODO: Add the GitHub Project board link once the board exists.

# Scope

## In scope for Draft 1
1. User accounts with authentication.
2. Interactive video player that pauses at defined timestamps and gates progression on answering questions.
3. Gamification: point system + leaderboard backed by persistent storage.
4. Adaptive-scaffolding assessment component (branching support based on performance).
5. BFS visualization: backend-computed traversal steps animated node-by-node on the frontend, with step controls.
6. Multi-mode content delivery (video / text / interactive) as a content-system capability.
7. REST API connecting frontend and backend.
8. GitHub repository with build/run/deploy instructions.
9. Placeholder lesson/content (videos, text, questions, graph scenarios) seeded via fixtures; real content is substituted later.

## Out of scope for Draft 1 **[PROVISIONAL]**
- Content authoring UI / admin dashboard (content seeded via fixtures/config initially).
- Topics beyond Graphs + BFS (e.g. DFS, Dijkstra, trees).
- Multi-course or multi-tenant support.
- Mobile-native apps (responsive web only).
- Social features beyond the leaderboard (comments, friends, chat).
- Offline mode / PWA installability.
- Production-grade analytics pipeline.

## Success criteria (engineering) **[PROVISIONAL]**
- A student can complete the full flow end-to-end in a deployed environment.
- BFS steps returned by the backend render a correct, repeatable animation.
- Points and leaderboard persist across sessions and reflect recorded events.
- Assessment branches to a scaffolding path when performance is below a configurable threshold.

# System Architecture

## High-level architecture

```
Browser
  │  HTTPS, one origin: ctrlacademy.co.za (production), staging.ctrlacademy.co.za (staging)
  ▼
Coolify's Traefik proxy (on our server; Let's Encrypt certificates, Cloudflare DNS)
  ▼
web container: nginx
  ├─ /            React + TypeScript SPA (Vite build)
  ├─ /media/      lesson videos (static files, served with range requests)
  └─ /api/*  ──►  api container: FastAPI on Uvicorn
                    routers → services → SQLAlchemy models
                    BfsEngine (pure Python module)
                      ▼
                  db container: PostgreSQL 18 (persistent volume, nightly pg_dump)
```

The three containers are defined in `docker-compose.yml`, and Coolify deploys that file as it is.
nginx serves the SPA and forwards `/api` to the API, so the browser only ever talks to one origin.
That removes the need for CORS and for an API base URL in the frontend.

## Tier responsibilities
- **Frontend (client tier):** presentation, interaction, animation, client-side validation. Holds no business authority over scores — it reports events; the backend decides and persists.
- **Backend (application tier):** authoritative logic — authentication, BFS computation, scoring rules, assessment branching, content retrieval, persistence orchestration.
- **Data tier:** durable storage of structured data; media served from a static/object store rather than the database.

## Key architectural decisions
- **Thin client for authority-bearing logic.** Score/assessment decisions are server-side to prevent client tampering and keep rules in one place.
- **BFS computed server-side.** Guarantees a single correct implementation (the canonical algorithm being taught) and keeps the frontend a pure renderer of returned steps.
- **Stateless API with token auth.** Enables horizontal scaling and simple deployment. The token travels in an httpOnly cookie (§5).
- **Content as data.** Lessons, questions, and graph scenarios are stored/configured as data so new content does not require frontend code changes.

# Technology stack

| Layer | Choice | Rationale |
|---|---|---|
| Backend language | **Python 3.12** | Team decision. Good for algorithm code and fast API development. |
| Web framework | **FastAPI** | Pydantic validation, typed request/response models, OpenAPI docs generated at `/api/docs`, which serve as the frontend contract. |
| ASGI server | **Uvicorn** | Runs directly as the API container's process. Docker restarts it if it crashes, so it needs no separate process manager. |
| Validation | **Pydantic v2** | Comes with FastAPI. Validates every request at the API boundary. |
| ORM and migrations | **SQLAlchemy 2.1** + **Alembic** | Typed models. Migrations are applied automatically when the API container starts (`alembic upgrade head`), so a migration that fails stops the deploy instead of running against the wrong schema. Baseline revision `0001` is in place. |
| Database | **PostgreSQL 18** in every environment | Local development runs the same Postgres in Docker. Tests use in-memory SQLite, so they run without a database server. Using one database engine everywhere avoids JSON and enum behaviour differing between dev and production. |
| Auth | **JWT** (PyJWT) in an **httpOnly, Secure, SameSite=Lax cookie**; passwords hashed with **Argon2** (pwdlib) | JWT as in Draft 1. Because the SPA and API share one origin, a cookie is simpler than an `Authorization: Bearer` header, and JavaScript can't read it, so an XSS bug can't steal the token. pwdlib replaces passlib: passlib is no longer maintained and breaks with current bcrypt releases, and FastAPI's own documentation now uses pwdlib. Email is required. Password reset and refresh tokens are future work. |
| Frontend language | **TypeScript 7** | Team decision. Type safety across the UI and the API client. |
| Frontend framework | **React 19** | Team decision, and what the scaffold already uses. |
| Build tool | **Vite 8** | Fast dev server with hot reload; the dev server proxies `/api` to the local API, so dev also uses one origin. |
| Routing | **React Router** | Client-side routing for the multi-view SPA. nginx already serves `index.html` for unknown paths. |
| Server state | **TanStack Query** | Data fetching and caching against the REST API. |
| Graph rendering | **SVG via D3** | As Draft 1: for graphs of up to about 50 nodes, SVG is simpler than Canvas (one DOM element per node and edge, easy per-element transitions, highlighting and click handling). |
| Video | **HTML5 `<video>`**, self-hosted MP4 (H.264) with WebVTT captions | The player needs full control to pause at checkpoints and block seeking past them. An embedded YouTube player would add adverts, recommendations and a dependency outside our control during the demo. Captions also provide the `text` mode for each video. |
| Testing (backend) | **pytest** with FastAPI `TestClient`, warnings treated as errors | Unit tests for the BfsEngine and services, plus API tests against a fresh SQLite database that every migration has been applied to. |
| Testing (frontend) | **Vitest** + **React Testing Library** | Native fit with Vite; component and logic tests, with coverage reported in CI. |
| End-to-end testing | **Playwright** | Walks through the full student flow (log in, lesson, checkpoint, BFS, assessment, scaffold) in a real browser against a running stack. |
| Lint and format (Python) | **ruff** (format + lint, including the bandit security rules and the FastAPI rules) and **mypy --strict** | Enforced in CI. |
| Lint and format (TypeScript) | **oxlint** (correctness, suspicious and perf rules plus the React, import, jsx-a11y and Vitest plugins; warnings fail the build) and **Prettier** | oxlint replaces ESLint: it is already configured and runs in under a second. The `jsx-a11y` plugin enforces part of the accessibility requirements (NFR-A). |
| CI | **GitHub Actions** | On every PR and on every push to `staging` and `master`: format, lint, types, tests and builds for both apps, and a build of the Docker images. A `branch-flow` check rejects PRs into `master` that don't come from `staging`. Dependabot opens weekly update PRs into `staging`. |
| Hosting | **Coolify** on the team's server, **Docker Compose** build pack | Coolify builds and deploys on every push: `staging` → staging.ctrlacademy.co.za, `master` → ctrlacademy.co.za. Its Traefik proxy terminates HTTPS. Staging sits behind a team-password page so the public can't see unfinished work. |

# Functional Requirements

Each feature is broken into concrete, testable capabilities. IDs (FR-x.y) are for traceability in later drafts.

## Interactive Video (FR-1)
- **FR-1.1** Play a lesson video with standard controls (play/pause/seek within allowed bounds).
- **FR-1.2** Pause automatically at configured timestamps ("checkpoints") defined per video.
- **FR-1.3** At a checkpoint, present one or more questions tied to that checkpoint.
- **FR-1.4** At a checkpoint the student submits an answer and receives **immediate feedback**. A wrong answer does **not** hard-block or lock the student out: they may **retry**. Playback does not resume until the checkpoint question is answered **correctly** (gate policy = `retry_until_correct`). There is no permanent lockout.
- **FR-1.5** Record **each attempt** (correct and incorrect) at a checkpoint as a progress event and route it to scoring (scoring distinguishes first-attempt-correct from retry-correct — see FR-2).
- **FR-1.6** Resume playback from the checkpoint once the question has been answered correctly.
- **FR-1.7** Prevent seeking past an unanswered (not-yet-correct) checkpoint.

## Gamification: Points + Leaderboard (FR-2)
- **FR-2.1** Award points for defined actions per a server-side rules table. **Draft 1 default rules (tunable, stored server-side):**

  | Action | Points |
  |---|---|
  | Correct checkpoint answer (first attempt) | 10 |
  | Correct checkpoint answer on retry (not first attempt) | 5 |
  | Completing a lesson | 25 |
  | Passing an assessment | 50 |
  | Completing the scaffolding path | 15 |

  These values are the Draft-1 defaults and are intended to be tuned; they live in a server-side rules table/config, not in the client.
- **FR-2.2** Persist per-user cumulative score and the underlying scoring events.
- **FR-2.3** Expose the current user's score and breakdown.
- **FR-2.4** Provide a leaderboard ranking users by score (top-N + the current user's rank).
- **FR-2.5** Scoring is computed/validated server-side; client reports events only.
- **FR-2.6** Leaderboard identity/privacy: each student chooses a **display name / handle** at signup, shown on the public leaderboard. A student may opt to appear **anonymised** on the public leaderboard (`is_anonymous_on_leaderboard` flag); when set, their handle is replaced with an anonymised label while their own rank remains visible to them.

## Adaptive-Scaffolding Assessment (FR-3)
- **FR-3.1** Deliver an assessment (set of questions) on Graphs + BFS.
- **FR-3.2** Evaluate answers server-side and compute a performance measure.
- **FR-3.3** If performance is below a **single, configurable pass/fail threshold**, branch the student into a **scaffolding path** (additional/alternative content or easier guided questions) before the lecture.
- **FR-3.4** If performance meets the threshold, mark the topic ready and record completion.
- **FR-3.5** Persist assessment attempts and results for scoring and progress.
- **FR-3.6** Draft 1 uses a **single global pass/fail threshold** only (configurable). The `scaffold_rules` JSON shape is retained for forward-compatibility, but Draft 1 exercises only the global-threshold branch. **Per-concept weakness detection (mapping specific weaknesses to targeted scaffolds) is explicitly deferred to Draft 2.**

> *Note:* The pedagogical justification for scaffolding is intentionally out of scope here; this section specifies only the engineering mechanism (thresholded branching over content).

## BFS Visualization (FR-4)
- **FR-4.1** Load a graph scenario (nodes, edges, directedness, start node) from the backend.
- **FR-4.2** Request a computed BFS traversal from the backend for a given scenario + start node.
- **FR-4.3** Render the graph (nodes + edges) in the browser.
- **FR-4.4** Animate the BFS step-by-step: current node, visited set, queue state, and newly discovered neighbours per step.
- **FR-4.5** Provide playback controls: step forward, step back, play/pause, reset, and speed control. (Back-stepping is supported in Draft 1 — enabled cheaply by local playback over precomputed steps.)
- **FR-4.6** Display auxiliary state (queue contents, visited order) alongside the animation.
- **FR-4.7** Support a small library of **predefined** graph scenarios for Draft 1. **Custom student-input graphs are deferred to Draft 2+** (noted future item; see §14).

## Multi-Mode Content Delivery (FR-5)
- **FR-5.1** Represent a lesson as a set of content items each tagged with a mode: `video`, `text`, or `interactive`.
- **FR-5.2** Serve the content items for a lesson so the frontend can present available modes.
- **FR-5.3** Allow the student to switch between available modes for the same concept.
- **FR-5.4** Track which modes/items a student has engaged with (for progress/scoring). **[PROVISIONAL]**

# Non-Functional Requirements

## Performance
- **NFR-P1** BFS computation for Draft 1 scenario sizes (≤ ~50 nodes) returns in well under 200 ms server-side.
- **NFR-P2** API p95 latency target < 300 ms for non-media endpoints under light load. **[PROVISIONAL target]**
- **NFR-P3** Frontend BFS animation sustains a smooth frame rate for Draft 1 graph sizes; animation is driven by precomputed steps (no per-frame server calls).
- **NFR-P4** Video media served from a static/CDN-style host, not proxied through the API.

## Usability
- **NFR-U1** Responsive layout for desktop and tablet widths.
- **NFR-U2** Clear, consistent controls for video, BFS stepping, and assessment navigation.
- **NFR-U3** Visible feedback for scoring events and assessment outcomes.

## Security & Authentication
- **NFR-S1** Passwords stored only as salted hashes (Argon2, via pwdlib).
- **NFR-S2** Authenticated endpoints require a valid **JWT in the session cookie**; authorization checks tie resources to the owning user. Email is required as account identity (used for recovery in later drafts). Password reset and refresh tokens are **deferred to Draft 2**.
- **NFR-S3** All traffic over HTTPS in deployed environments.
- **NFR-S4** Server-side validation of all inputs (Pydantic schemas); never trust client-reported scores/results.
- **NFR-S5** No secrets in the repository; configuration via environment variables.
- **NFR-S6** Standard protections: the session cookie is httpOnly, Secure and SameSite=Lax; state-changing requests require JSON bodies (blocking cross-site form posts); parameterised queries via the ORM; rate limiting on auth endpoints **[PROVISIONAL]**. The app and the API share one origin, so no CORS is configured.

## Maintainability
- **NFR-M1** Layered backend (routers → services → data) with the BfsEngine isolated from web concerns and unit-testable in isolation.
- **NFR-M2** Typed boundaries both sides (Pydantic + TypeScript); API types kept in sync (consider generating a TS client from OpenAPI **[PROVISIONAL]**).
- **NFR-M3** ruff, mypy --strict, oxlint and Prettier enforced in CI on every PR.
- **NFR-M4** Database migrations tracked with Alembic.

## Accessibility **[PROVISIONAL]**
- **NFR-A1** Keyboard operability for primary controls (video, stepping, assessment).
- **NFR-A2** Sufficient colour contrast; BFS state not conveyed by colour alone (also labels/shapes).
- **NFR-A3** Semantic HTML and ARIA roles for custom controls.
- **NFR-A4** Captions/transcripts for videos (ties into the `text` content mode).

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

# API Design (REST)

Base path: `/api`. JSON over HTTPS. Auth via the session cookie set by `/api/auth/login`, except where noted. Response/request bodies validated by Pydantic. Endpoint list is **[PROVISIONAL]** and will firm up with the OpenAPI schema.

## Auth
| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/auth/register` | public | Create a user account. |
| POST | `/api/auth/login` | public | Check credentials and set the session cookie. |
| POST | `/api/auth/logout` | user | Clear the session cookie. |
| GET | `/api/auth/me` | user | Current user profile. |

## Lessons & Content
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/lessons` | user | List lessons. |
| GET | `/api/lessons/{lessonId}` | user | Lesson detail. |
| GET | `/api/lessons/{lessonId}/content` | user | Content items (all modes) for a lesson. |
| GET | `/api/videos/{videoId}` | user | Video metadata + checkpoints (not the media bytes). |

## Interactive Question Answering
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/checkpoints/{checkpointId}/questions` | user | Questions for a video checkpoint. |
| POST | `/api/questions/{questionId}/answer` | user | Submit an answer; returns correctness + gate decision; records a ProgressEvent. |

## BFS Computation / Stepping
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/graphs` | user | List available graph scenarios. |
| GET | `/api/graphs/{scenarioId}` | user | Scenario detail (nodes/edges). |
| POST | `/api/graphs/{scenarioId}/bfs` | user | Compute BFS from a given `startNode`; returns ordered steps for animation. |

Example `POST /api/graphs/{scenarioId}/bfs` request/response:
```json
// request
{ "startNode": "A" }

// response
{
  "scenarioId": 1,
  "startNode": "A",
  "order": ["A", "B", "C", "D"],
  "steps": [
    {
      "index": 0,
      "action": "visit",
      "node": "A",
      "queueBefore": [],
      "queueAfter": ["B", "C"],
      "visited": ["A"],
      "discovered": ["B", "C"],
      "frontierEdges": [["A","B"], ["A","C"]]
    }
    // ...one entry per BFS step
  ]
}
```

## Scoring
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/me/score` | user | Current user's total + breakdown. |
| GET | `/api/me/progress` | user | Progress events / completion state. |

(Scores are mutated as a side effect of answer/assessment submissions, not by a direct client "add points" call.)

## Leaderboard
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/leaderboard` | user | Top-N ranked users + the current user's rank. |

## Assessment
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/lessons/{lessonId}/assessment` | user | Fetch the assessment (questions). |
| POST | `/api/assessments/{assessmentId}/submit` | user | Submit answers; server grades, decides branch, persists AssessmentResult, returns outcome + scaffold payload if branched. |
| GET | `/api/assessments/{assessmentId}/result` | user | Latest result for the current user. |

Example `POST /api/assessments/{assessmentId}/submit` response:
```json
{
  "assessmentId": 7,
  "score": 0.55,
  "passed": false,
  "branchTaken": "scaffold",
  "scaffold": {
    "reason": "below_threshold",
    "contentItemIds": [12, 15],
    "guidedQuestions": [31, 32]
  }
}
```

## Conventions **[PROVISIONAL]**
- Standard HTTP status codes; error bodies `{ "detail": "..." }`.
- Pagination for list endpoints (`?limit=&offset=`) where needed (leaderboard, lessons).
- OpenAPI/Swagger auto-published at `/api/docs` (FastAPI) and used as the frontend contract.

# BFS Engine Design

## Responsibilities
A self-contained `BfsEngine` module in the backend, independent of web/HTTP concerns, that:
1. Accepts a graph scenario (nodes, edges, directedness) and a start node.
2. Produces the BFS traversal **order** and a list of **steps** rich enough for the frontend to animate without re-deriving algorithm logic.

## Graph representation
- Input (from `GraphScenario`): `nodes` as a list of ids/labels; `edges` as `{source, target, weight?}`; `directed` flag.
- Internal: an **adjacency list** `dict[node, list[node]]`. For undirected graphs, each edge is inserted in both directions. Neighbour ordering is made **deterministic** (e.g. sorted by node id/insertion order) so animations are reproducible and testable.

## Algorithm & step emission
Standard BFS using a FIFO queue (`collections.deque`) and a `visited` set. On each loop iteration the engine emits a **step record** capturing observable state:

```
dequeue current node
emit step: { index, action: "visit", node: current,
             queueBefore, visited(after marking),
             discovered: [newly enqueued neighbours this step],
             queueAfter, frontierEdges: [(current, neighbour) ...] }
for each neighbour of current (deterministic order):
    if neighbour not visited and not already queued:
        mark discovered, enqueue
```

The returned payload (see §9.4) contains:
- `order`: the final visitation order (teaching the core result),
- `steps`: per-step snapshots (queue before/after, visited set, newly discovered nodes, edges explored) so the frontend can highlight nodes/edges and show queue state at each step.

## Design properties
- **Deterministic** output for a given scenario + start node (reproducible animations, easy snapshot tests).
- **Pure/stateless** computation (no DB access inside the engine; scenario data passed in).
- **Validated inputs** (start node exists, edges reference known nodes) — malformed scenarios rejected with a clear error.
- **Precomputed, not streamed:** the entire step list is returned in one response; the frontend controls playback locally (supports step-back and scrubbing without extra calls). This is settled for Draft 1 given the confirmed small-graph scope (≤ ~50 nodes); it may be revisited only if graphs grow substantially in a later draft.

## Testing
- Unit tests over known graphs with asserted `order` and `steps` (directed and undirected; disconnected graph handling; single-node; start-node validation).

# Frontend Component Breakdown (React + TypeScript)

**[PROVISIONAL]** — component tree will evolve. Organised by feature.

- **App shell**
  - `AppRouter` — route definitions.
  - `AuthProvider` — holds auth token/session; guards routes.
  - `ApiClient` — typed REST client (fetch wrapper; consider OpenAPI-generated types).
- **Auth**
  - `LoginPage`, `RegisterPage`, `ProtectedRoute`.
- **Lesson & content**
  - `LessonListPage`, `LessonPage`.
  - `ContentModeSwitcher` — toggles between `video` / `text` / `interactive` items.
  - `TextContentView`, `InteractiveContentView`.
- **Interactive video**
  - `InteractiveVideoPlayer` — wraps the HTML5 video element, enforces checkpoint pauses and seek limits.
  - `CheckpointQuestionOverlay` — renders checkpoint question(s), gates resume.
- **BFS visualizer**
  - `GraphScenarioLoader` — fetches scenario + requests BFS steps.
  - `GraphCanvas` — renders nodes/edges as **SVG via D3** (layout + transitions).
  - `BfsAnimator` — consumes `steps`, drives highlighting.
  - `StepControls` — forward/back/play/pause/reset/speed.
  - `BfsStatePanel` — shows queue, visited order, current node.
- **Assessment**
  - `AssessmentPage`, `QuestionRenderer` (by question type), `AssessmentResultView`, `ScaffoldPanel` (renders returned scaffold content).
- **Gamification**
  - `ScoreBadge` / `PointsIndicator`, `LeaderboardPage`.
- **Shared**
  - `QuestionRenderer`, `Spinner`, `ErrorBoundary`, `Toast`/feedback components.

# Repository structure

Repository: `MatthewEls/cos750-project`. Folders marked *(planned)* don't exist yet.

```
cos750-project/
├─ README.md                    run it, checks, database, branches and deploys
├─ docker-compose.yml           web + api + db, deployed by Coolify as it is
├─ docker-compose.local.yml     publishes ports for local use
├─ .env.example
├─ .github/
│  ├─ workflows/ci.yml          web, api and compose jobs
│  ├─ workflows/branch-flow.yml
│  ├─ dependabot.yml
│  └─ pull_request_template.md
├─ scripts/check.sh             every CI check locally; --fix formats first
├─ api/
│  ├─ Dockerfile                runs migrations, then Uvicorn
│  ├─ requirements.txt          runtime dependencies (pinned)
│  ├─ requirements-dev.txt      + pytest, ruff, mypy
│  ├─ pyproject.toml            ruff, mypy and pytest settings
│  ├─ alembic.ini
│  ├─ migrations/versions/      one file per schema change
│  ├─ app/
│  │  ├─ main.py                FastAPI app, router registration
│  │  ├─ db.py                  engine, Base, DbSession dependency
│  │  ├─ models/                SQLAlchemy models
│  │  ├─ schemas/               Pydantic request/response models (planned)
│  │  ├─ routers/               auth, content, questions, bfs, scoring, leaderboard, assessment (planned)
│  │  ├─ services/              AuthService, ContentService, ScoringService, AssessmentService (planned)
│  │  ├─ bfs/engine.py          BfsEngine: pure, tested in isolation (planned)
│  │  └─ seed/                  lessons, questions, graph scenarios, demo accounts (planned)
│  └─ tests/
├─ web/
│  ├─ Dockerfile                Vite build, then nginx
│  ├─ nginx.conf                SPA, /api proxy, /media, /healthz
│  ├─ staging-gate.sh, gate/    staging team-password page
│  ├─ package.json, vite.config.ts, .oxlintrc.json, .prettierrc.json, .nvmrc
│  └─ src/
│     ├─ main.tsx, App.tsx
│     ├─ api/                   typed API client (planned)
│     ├─ auth/                  (planned)
│     ├─ components/            shared components (planned)
│     ├─ features/              lessons, video, bfs, assessment, gamification (planned)
│     └─ test/setup.ts
├─ e2e/                         Playwright tests (planned)
├─ assets/                      Ctrl Group logo pack
└─ docs/
   ├─ se/se-document.md         this document
   ├─ id/id-document.md         the ID document
   ├─ build/                    builds both into PDFs (npm run pdf)
   ├─ spec/, references/, course-material/
   └─ deploy/coolify.md
```

# Build, run and deploy

## Local development

The whole stack, built the same way Coolify builds it:

```bash
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
# http://localhost:8080
```

With hot reload, Postgres in Docker and the rest on your machine:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d db

cd api && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/alembic upgrade head
.venv/bin/python -m app.seed      # placeholder content and demo accounts (planned)
.venv/bin/uvicorn app.main:app --reload            # http://localhost:8000/api/docs

cd web && npm install && npm run dev               # http://localhost:5173, proxies /api to :8000
```

## Checks

`scripts/check.sh` runs everything CI runs except the Docker build: Prettier, oxlint, Vitest and
the production build for `web`; ruff, mypy and pytest for `api`. `scripts/check.sh --fix` formats
and auto-fixes first.

## Branches, CI and review

- Work happens on a feature branch, which goes into `staging` through a reviewed PR. `staging` goes into `master` through another PR.
- CI must pass before merging. A PR into `master` from any branch other than `staging` fails the `branch-flow` check.
- A merge into `staging` deploys to staging.ctrlacademy.co.za, where the team checks it behind the team password before it is promoted.

## Deployment

- Coolify watches the repository and deploys on push using the Docker Compose build pack: `staging` → staging.ctrlacademy.co.za and `master` → ctrlacademy.co.za. Each environment has its own database and its own `POSTGRES_PASSWORD`.
- The API container applies pending migrations before serving, so schema changes reach each environment with its deploy.
- Postgres is backed up nightly by a Coolify scheduled task (`pg_dump`, kept for 14 days).
- Videos are stored in a `media` volume mounted into the web container and served by nginx at `/media/`, outside git and outside the image *(planned)*.
- Secrets are environment variables set in Coolify (database password, JWT secret, `STAGING_PASSWORD`). None are committed (`.env` is gitignored; only `.env.example` is in the repo).

# Assumptions, Risks, and Open Questions

## Assumptions
- Single student role for Draft 1; content is seeded via **placeholder fixtures** (no authoring UI yet); real lesson videos/content are added later.
- Graphs are small (≤ ~50 nodes), so full BFS step precomputation per request is acceptable and SVG/D3 rendering is appropriate.
- Scoring authority is server-side; the client only reports events.
- One topic (Graphs + BFS) with one lesson and one assessment is sufficient for Draft 1.
- **Team size is 7.** This allows slightly more of the previously-provisional scope to be committed to Draft 1 (e.g. confirmed Postgres/Docker deployment, concrete scoring and gating), but the draft is kept honest and does not over-commit — advanced items (per-concept scaffolding, custom graphs, password reset/refresh tokens) remain deferred.

## Risks
- **Interactive video gating** — reliably enforcing pause/seek limits and the `retry_until_correct` gate across browsers can be fiddly; may need a vetted player library.
- **Adaptive scaffolding complexity** — rule-driven branching can balloon; Draft 1 deliberately uses a single global threshold, with per-concept weakness detection deferred to Draft 2.
- **Media hosting** — video storage/bandwidth for real content is not yet sized (placeholders used in Draft 1); affects deploy cost once real media lands.
- **Video production** — who records the lesson videos, and by when. Without them the interactive video feature can only be demonstrated with placeholders.
- **Scope creep** — custom graph input, multiple topics, and an authoring UI are tempting but out of scope for Draft 1.

## Resolved decisions (previously open)
The following Draft-1 open questions have been decided and are now reflected throughout the document:
1. **Graph rendering** → **SVG via D3** (simpler for ≤~50-node graphs; §5, §11).
2. **Database** → **PostgreSQL** in every environment, including local development; SQLite only inside the tests (§4, §5, §13).
3. **Deployment** → **Docker Compose on Coolify**, already live: staging.ctrlacademy.co.za and ctrlacademy.co.za, with Traefik terminating HTTPS and nginx serving the app and proxying `/api` (§13.4).
4. **Video gating policy** → **`retry_until_correct`**: wrong answers give feedback and allow retry, no hard-block/lockout; each attempt recorded (FR-1, §8).
5. **Scaffolding granularity** → **single global pass/fail threshold** in Draft 1; per-concept weakness detection deferred to Draft 2 (FR-3, §8).
6. **Leaderboard identity** → required **display name/handle** at signup with an **anonymised** opt-in (`is_anonymous_on_leaderboard`) (FR-2, §8).
7. **Scoring rules** → concrete Draft-1 default rules table (10 / 5 / 25 / 50 / 15), tunable, server-side (FR-2).
8. **Auth scope** → **email required**; JWT access tokens; password reset and refresh tokens deferred to Draft 2 (§5, §7.3, §8).
9. **Content source** → **placeholder content** seeded via fixtures for Draft 1; real content later (§13, §14.1).
10. **Team size** → confirmed **7** (§14.1).
11. **Custom graphs** → **deferred to Draft 2+**; predefined scenario library for Draft 1 (FR-4.7).

## Open questions remaining for Draft 2
- **Per-concept weakness detection** for scaffolding (mapping specific weaknesses → targeted scaffolds) — the `scaffold_rules` JSON shape is ready for it.
- **Custom student-input graphs** — UI, validation, and backend acceptance of student-authored scenarios.
- **Auth hardening** — password reset flow and refresh-token strategy.
- **Content authoring** — admin/author role and authoring UI to replace fixtures; sizing of real video media hosting/bandwidth.
- **Additional topics** beyond Graphs + BFS (DFS, Dijkstra, trees) and any multi-lesson/multi-assessment structure.
- **Materialised leaderboard** / caching if leaderboard query performance becomes a concern at larger user counts.
- **Rate limiting** on auth endpoints and other hardening noted as provisional in §7.3.

*End of DRAFT 1 — Software Engineering design document. Instructional-design content is maintained separately in the ID document per the exam specification.*
