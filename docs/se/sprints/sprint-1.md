# Sprint 1: One complete path

**Dates:** 2 – 8 November 2026
**Goal:** one student can register, work through a module, take the mastery check and be sent to the review path for any objective marked "not yet", with placeholder content, deployed to staging (SE document §2.3).
**Status:** reviewed at the Sprint 1 review and Sprint 2 planning on 8 November 2026 (19:00). This record was compiled afterwards from the project board, the merged pull requests and the team's Discord.

## What happened

| Date | Event | Evidence |
|---|---|---|
| 2 Nov | Accounts (register, log in, log out), the UI kit and brand guide; five rounds of security review on the accounts, each with its attacks kept as tests; the API made to answer "busy" under load instead of stalling | PRs #42 – #49 |
| 3 Nov | The code runner built, attacked on staging in four rounds, then **removed**: code activities are checked by comparison with the solution, and no student code runs (decision §15.3) | PRs #51 – #61, #88 |
| 3 Nov | Branch rules for `staging` and `master`, and a push guard | PR #52 |
| 5 Nov | **Weekly check-in** (recorded) | Appendix B |
| 5 Nov | The BFS engine and its steps endpoint; the narrated video player; the staff portal for videos, accounts and staff members, with video export and import; the first demo account | PRs #89, #91, #94, #95, #97 |
| 6 Nov | Private points, badges, the badge shelf and opting out | PR #101 |
| 7 Nov | 90% coverage enforced on the code that decides results; trace tables checked step by step against the engine; frontend API types generated from the OpenAPI schema; matching, fix-the-bug and choose-tests activities | PRs #99, #103, #104, #112 |
| 8 Nov | The content model; the mastery check and report; the review path; the evaluation event log and CSV exports; the module map, module page and progress tracking; the account menu and profile; prediction in the visualiser; the code activity screens; three more demo accounts; module 3's content | PRs #105 – #110, #113 – #118, #122, #123 |
| 8 Nov | The pilot kit and the ID team's generative AI record | PR #124 |
| 8 Nov | **Sprint 1 review and Sprint 2 planning** | Appendix B |

Table: Sprint 1 timeline.

## Delivered

- The sprint goal: a student can register, open the module map, work through a module's segments and activities with hints and feedback, take the mastery check, see a report per objective and open the review path for an objective marked "not yet". It ran on staging with placeholder content, and module 3's real content arrived on the last day.
- The BFS engine with its tests, and trace tables marked against it.
- Every code activity kind checked by comparison: Parsons, fill-in, fix the bug and choose tests.
- Private points and badges, the staff portal, the evaluation export and the demo accounts.
- Fifty-one pull requests merged into `staging`, each reviewed by a teammate.

## Decisions

| Date | Decision | Recorded in |
|---|---|---|
| 3 Nov | Remove the code runner; code activities are ordering and fill-in, checked by comparison | SE document §15.3 (decision 6), §14.6 |
| 8 Nov | Staff, the ID team above all, edit content in the staff portal, so that findings can be fixed the same day without a pull request | SE document §15.3 (decision 9) |

Table: Decisions made in Sprint 1.

## Not finished, carried into Sprint 2

- The content of modules 0, 1, 2, 4, 5 and 6 (issues #26, #28, #83 – #86).
- Activities shown inside their module segments, and a segment that must be done before the student moves past it.
- The end-to-end tests in three browsers (issue #35) and the narrated videos (issue #37).

## Review

Held at the meeting on 8 November. The sprint goal was met on staging, with placeholder content in every module but module 3.

## Retrospective

Compiled from the sprint's record: the board, the pull requests and the team's Discord.

**What went well**
- The core of the app was built in one week: the engine, the mastery check, the review path and every activity kind.
- Security was tested before features were built on top of it, and the code runner was dropped the same day its risk was clear, instead of being patched again.
- Reviews were quick: 42 of the 51 pull requests were merged within a day of being opened, half of them within an hour.

**What to change**
- Most of the pull requests (37 of 51) came from one member. Building and reviewing depended on one person.
- Branches drifted from `staging`. A long-lived branch carried a database migration that clashed with one already merged, and it had to be renumbered before it could merge.
- Content arrived on the last day, so most modules were still placeholders at the review.

**Action for Sprint 2**
- The ID team writes content straight into the staff portal and fixture files, one module per member, so content no longer waits on engineers.
