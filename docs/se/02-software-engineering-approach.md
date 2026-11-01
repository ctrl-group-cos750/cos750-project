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
