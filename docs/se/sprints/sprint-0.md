# Sprint 0: Foundation

**Dates:** 22 October – 1 November 2026
**Goal:** choose the topic and the way of working, and have a repository, hosting and documents that the whole team can build on from Sprint 1.
**Status:** draft review and retrospective, for the team to confirm at the meeting on 1 November 2026 (19:00).

## What happened

| Date | Event | Evidence |
|---|---|---|
| 22 Oct | Examination specification issued; repository created | Spec in `docs/spec/`; first commit |
| 23 Oct | Specification, CS2023 and repository conventions added; feature → `staging` → `master` branch flow enforced in CI | PRs #1, #2, #3 |
| 25 Oct | **Initial meeting** (Discord). Decided: graphs + BFS; Python and TypeScript; Scrimba-style lessons with gamification; software engineers Reece, Ayanda and Matthew, everyone else instructional design; a weekly call on Thursdays at 19:00 | #general, 25 Oct |
| 25 Oct | Domain `ctrlacademy.co.za` secured for the app | #general, 25 Oct |
| 26 Oct | Separate Discord channels for the software engineers and the instructional designers | #general, 26 Oct |
| 29 Oct | ID document draft 1 shared with the team | #instructional-designers, 29 Oct |
| 31 Oct | React + FastAPI + PostgreSQL scaffold; staging and production hosted on Coolify; production shows a "coming soon" page until the first release | PR #5 |
| 1 Nov | Database layer with migrations, a real CI (formatting, linting, types, tests, image builds), nightly backups, team login on staging | PR #6 |
| 1 Nov | SE document draft 1 shared | #software-engineers, 1 Nov |
| 1 Nov | Course material organised in the repository; SE and ID documents moved into the repository as Markdown, built into branded PDFs, latest PDFs published from `staging` | PRs #7 – #10 |
| 1 Nov | SE document draft 2: Scrum, the stack as built, requirements aligned with the ID document, testing strategy, diagrams | PRs #11, #12 |
| 1 Nov | Repository moved to the `ctrl-group-cos750` organisation; project board created with the Sprint 1 and Sprint 2 backlog (issues #13 – #39); group invited to the organisation | Board; #general, 1 Nov |
| 1 Nov | Matthew chosen as Scrum Master | PR #40 |

Table: Sprint 0 timeline.

## Delivered

- A running platform: staging (behind the team login) and production at ctrlacademy.co.za, deployed automatically from `staging` and `master`.
- A repository the team can work in safely: branch flow, PR template, CI that checks both apps on every PR, database migrations that run on deploy, nightly backups.
- Both documents in the repository, reviewed through PRs and built into PDFs in one format.
- A prioritised backlog for Sprints 1 and 2, with every item traced to the SE document's requirements.

## Decisions

| Date | Decision | Recorded in |
|---|---|---|
| 25 Oct | Topic: graphs and breadth-first search | SE document §1 |
| 25 Oct | Languages: Python and TypeScript | SE document §5 |
| 25 Oct | Roles: three software engineers, four instructional designers | SE document §2.2 |
| 25 Oct | Weekly Thursday call at 19:00 | SE document §2.5 |
| 1 Nov | Scrum with one-week sprints, Monday to Sunday; no Product Owner; Matthew is Scrum Master | SE document §2 |
| 1 Nov | Tech stack as built; JWT in an httpOnly cookie; Argon2 password hashing | SE document §5 |
| 1 Nov | Student code runs on our server in an isolated runner container | SE document §4, NFR-S7 |
| 1 Nov | Narrated videos without a presenter; private points and badges instead of a leaderboard; email and password accounts | SE document §15.3 |
| 1 Nov | Pilot by team members on 10–11 November; 90% coverage enforced on the code that decides results | SE document §14 |

Table: Decisions made in Sprint 0.

## Not finished, carried into Sprint 1

- Deploys from the organisation: Coolify's GitHub App on the organisation and both apps repointed (issue #24).
- The ID document's sections still marked "need input from the team": introduction, accessibility, motivation, evaluation, and the instructional design part of the generative AI record.

## Review

TODO: Confirm at the meeting that the delivered items above are accepted.

## Retrospective (draft for the team to change)

**What went well**
- The big decisions were made early, at the meeting on 25 October, so the documents and the setup had a clear direction.
- The platform, CI and hosting are in place before any feature work, so Sprint 1 starts building features straight away.
- The ID document draft was thorough and early, which let the SE requirements be traced to it.

**What to change**
- Most of the setup happened in the last two days of the sprint, and through one person. Sprint 1 spreads the work through the board, with every item owned by someone.
- Access was slow: the first repository invitations expired before everyone accepted them.
- Decisions were spread across Discord channels; they are now recorded in the SE document and in these sprint records.

**One action for Sprint 1**
- Every Sprint 1 item has an owner by Monday morning, and everyone posts a short daily stand-up in Discord.

TODO: Change or confirm the retrospective at the meeting.
