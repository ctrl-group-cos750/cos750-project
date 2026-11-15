# Sprint 2: Real content and the full feature set

**Dates:** 9 – 15 November 2026
**Goal:** the real content in every module, all the features in the SE document, and a release to production on 13 November (SE document §2.3).
**Status:** reviewed at the final meeting before the demo on 15 November 2026 (19:00). This record was compiled from the project board, the merged pull requests and the team's Discord.

## What happened

| Date | Event | Evidence |
|---|---|---|
| 10 Nov | Content: modules 1 and 2 | PRs #126, #127 |
| 11 Nov | Content: modules 0, 4 and 6; retrieval questions for modules 2 to 6; the staff content editor; activities and videos inside their segments, and a segment that must be done before moving on; course progress in minutes; module locks on activities, hints and videos; module completion rewards; the trace table, fix-the-bug and choose-tests screens; a content pass so mastery items can't be gamed | PRs #125, #128 – #135, #157, #160 – #170 |
| 12 Nov | Support segments for a struggling student, with content for modules 1 to 4; review paths that teach again; the mastery check with one answer per item and two hints at most; graph answers drawn as graphs; evidence-based content; module 5's content; end-to-end and accessibility tests in Chromium, Firefox and WebKit; the content authoring guide | PRs #175 – #186, #189 |
| 12 Nov | Weekly call skipped by agreement; updates posted in Discord instead | Appendix A, Appendix B |
| 9–13 Nov | Team members work through the modules on staging and note what goes wrong; notes fixed in the PRs above | Discord; ID document §8.3 |
| 12–13 Nov | Expert review of the interface against usability heuristics | ID document §8.2 |
| 13 Nov | Content audit (issue #214) and its fixes: learner choice with open modules and the quick check, the skill profile, medals and the success moment | PR #215 |
| 13 Nov | Objective 8 assessed; the course's real length shown (about 180 minutes); follow-through marking in trace tables; the lecturer's "Before the lecture" page; restarting a module; the closing transfer task and two bonus quests; the demo script | PRs #195 – #213 |
| 13 Nov | **Release to production** (`staging` → `master`) | PR #218 |
| 15 Nov | **Final meeting before the demo** | Appendix B |

Table: Sprint 2 timeline.

## Delivered

- Real content in all seven modules, written by the ID team, with every answer checked by code in the tests.
- The features of the SE document, apart from those listed as known limitations (§15.5): the content editor, support segments, the quick check, retrieval questions, review paths, the skill profile, medals, badge levels, the study companion, refresher skipping, bonus quests and the narrated videos with their checkpoints.
- End-to-end and accessibility tests in three browsers.
- Sixty-four pull requests merged into `staging`, and the release to production on 13 November.

## Decisions

| Date | Decision | Recorded in |
|---|---|---|
| 13 Nov | Students choose where to start; a module is skipped only by passing its quick check | SE document FR-2.1, FR-8.2 |
| 13 Nov | Show the course's real length (about 180 minutes) rather than the planned 75 | ID document §4.4 |
| 13 Nov | Rewards already earned are never taken away when a rule is tightened | SE document FR-9.6 |

Table: Decisions made in Sprint 2.

## Not finished

- The items in the SE document's known limitations (§15.5).

## Review

Held at the final meeting before the demo on 15 November, with the release check, a walkthrough of both documents and a rehearsal of the presentation and demo.

## Retrospective

Compiled from the sprint's record: the board, the pull requests and the team's Discord.

**What went well**
- The ID team's content arrived in the sprint: every module had its real content by 12 November.
- The audit of 13 November was fixed the same day, and the fixes went out in the release.
- The app was tested end to end in three browsers before release.

**What to change**
- Walkthrough notes were spread across Discord messages and issues. One shared place for them would have made them easier to track and to report.
- The course was planned at 75 minutes and written at about 180. Timing content as it is written would have caught this earlier.
- The narrated videos were recorded last, from slides rather than the narration scripts, so their wording differs from the lessons in places.

**Action for the next round**
- Test with real novices before adding features, and time each module as it is written.
