# Presentation: speaker notes (#81)

Ten minutes, then the ten-minute demo (`demo-script.md`), then five minutes of questions
(examination specification). Every member presents a part. The split below is a **proposal**:
change names at the rehearsal, but keep each part to its time.

Build the PDF from the repository root with `node docs/presentation/build.mjs` (uses the
end-to-end tests' Playwright). Upload `slides.pdf` to ClickUP before the slot.

| Slide | Presenter (proposed) | Time | Cumulative |
|---|---|---|---|
| 1. Title | Matthew Els | 0:30 | 0:30 |
| 2. The learners | Joshua Wereley | 1:00 | 1:30 |
| 3. Eight objectives | Mohtashim Hussain | 1:00 | 2:30 |
| 4. ADDIE | Jacobus Hoogenboezem | 1:00 | 3:30 |
| 5. Theories on screen | Ayanda Juqu | 1:00 | 4:30 |
| 6. Scaffolding and mastery | Mohtashim Hussain | 1:15 | 5:45 |
| 7. Motivation | Joshua Wereley | 1:00 | 6:45 |
| 8. Scrum and architecture | Matthew Els | 1:00 | 7:45 |
| 9. Quality | Simphiwe Nhlapo | 1:00 | 8:45 |
| 10. Gaps and evaluation | Reece Schmidt | 1:00 | 9:45 |
| 11. Demo | Matthew Els (hand over) | 0:15 | 10:00 |

## 1. Title (0:30)

We are Control Group. Ctrl Academy prepares COS212 students for the graphs lecture: it teaches one
data structure, graphs, and one algorithm on it, breadth-first search, to students who have never
met either. Over the next ten minutes we show how we designed it as instructional designers and how
we built it as software engineers; then we show it working.

## 2. The learners (1:00)

Our learners are second-year COS212 students. From COS110 they know queues; they can read a Python
list and a loop. They have not seen a graph. A BFS lecture asks for three things at once: the
vocabulary, a mental model of the queue, and the code. So the app comes before the lecture, takes
about three hours in short modules, and ends with an honest report. Graphs, BFS and shortest paths
are core in CS2023's Algorithmic Foundations.

## 3. Eight objectives (1:00)

Each objective has a Bloom level, evidence the app collects, and a criterion. They climb from
Understand (define, identify) to Apply (map, trace, implement, find the shortest route) to
Evaluate (test and debug). The criterion is what the app checks, item by item: four of five, three
of four, at most one error in a trace. This is constructive alignment: the activity in a module and
the item in the mastery check exercise the same skill. Objective 8, the shortest route and why BFS
guarantees it, asks for the reason as well as the answer.

## 4. ADDIE (1:00)

We used ADDIE, because every phase leaves something you can check: the learner profile, Table 1,
the content files, the evaluation plan. We did not run it as a waterfall. Inside Develop we
prototyped: content went onto staging within days of being written, and what did not work went
back to Design. Every module follows Gagné's nine events: a problem to gain attention, the goals,
recall, a worked example, practice with feedback, assessment, and a transfer task at the end.

## 5. Theories on screen (1:00)

Cognitive load theory is the backbone: a novice learns more from a worked example than from
solving alone, so each new skill starts as one, and the help fades. Module 4 is the clearest case:
put BFS in order, then fill in three blanks, then nine. Module 1 starts the other way round, with
a problem before the definitions, which productive-failure research supports when the problem is
followed by teaching. And feedback always says why an answer is wrong.

## 6. Scaffolding and mastery (1:15)

The specification's hard requirement is an assessment that gives extra help to students who
struggle. Help comes at every level. In practice there is a four-level hint ladder, from a nudge to
the worked answer. A student who struggles inside a module is shown an extra worked example and
another question. The mastery check uses unseen items, one answer each, at most two hints. The
report gives each objective one of three results: met independently, met with support, or not
yet. A "not yet" opens a review path that teaches the objective again, with practice of the same
kind and fresh items. A student is ready for the lecture when nothing is "not yet".

## 7. Motivation (1:00)

We designed with Keller's ARCS model: attention with a real problem and videos that stop to ask;
relevance with graphs students know; confidence with clear goals, honest times and hints that
never leave anyone stuck; satisfaction with badges that each name a skill. Two choices come from
the research: no leaderboard, because comparison discourages the weakest students, the ones this
app is for; and badges can be turned off where they appear, because extrinsic rewards can crowd
out interest.

## 8. Scrum and architecture (1:00)

We ran Scrum in one-week sprints: Sprint 0 for the foundation, Sprint 1 for a complete path with
placeholder content, Sprint 2 for the real content. One board for engineers and designers, daily
stand-ups on Discord, a weekly call. Every change goes through a reviewed pull request into
staging, then to production. The content is data, so designers add questions without code, and
tests run every answer through the BFS engine. When we found a student could fake the hidden tests
in our code sandbox, we dropped running student code: the code activities are Parsons and
fill-in, checked on the server.

## 9. Quality (1:00)

Over two thousand API tests, nearly five hundred web tests, and end-to-end tests that walk the
whole student path in three browsers, with an accessibility scan of every page in light and dark
mode. The app works with a keyboard alone, on a phone and on a 4K screen. Login was
penetration-tested, and we keep only a name, an email address and progress.

## 10. Gaps and evaluation (1:00)

Three honest gaps. The content takes about three hours, not the 75 minutes we planned; the app now
tells students the real time, and the pilot will show what to cut. All practice happens in one
sitting; a spaced quiz on the day of the lecture would help retention. And explanations are
checked by multiple choice. We evaluate with a pilot (think-aloud, SUS, ARCS), item analysis of
the event log, and, with real students, a delayed post-test. Generative AI helped with code,
documents and content; every use is recorded with its prompts in the ID document.

## 11. Demo (0:15)

Hand over to the demo: `demo-script.md`.
