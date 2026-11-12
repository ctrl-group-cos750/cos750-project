# Demo script (#82)

Ten minutes, straight after the presentation. One person drives (proposed: Matthew Els), another
narrates each step (proposed: Joshua Wereley); swap at the rehearsal if you like. The narration is
short on purpose: let the screen do the work.

## Before the slot

- **Decide where the demo runs.** Production (ctrlacademy.co.za) has no demo accounts: they need
  `DEMO_PASSWORD`, which production deliberately doesn't set (SE document, deployment). Either set
  `DEMO_PASSWORD` on the production app in Coolify and redeploy (the seed creates the four demo
  accounts, which are left out of the evaluation data), or run the whole demo on staging
  (staging.ctrlacademy.co.za, team password `ctrlgroup`). Production must be on the same commit
  as staging either way: release staging → master after the last merge, then **freeze**: nothing
  is merged or deployed from the first rehearsal until after the demo (#82).
- **Videos:** upload the recorded videos (#37) through the staff portal before the freeze. If a
  video is missing, its segment shows the narration as text; skip step 4's video and show the
  checkpoint in the visualiser instead.
- **Browser:** a fresh profile, zoom 100%, light theme, window 1440 × 900 or a 1080p projector.
  Open these tabs in order before the slot: the landing page; the login page in a private
  window for each demo account (`new`, `mid`, `not-yet`, `ready` at `<key>@demo.example.com`);
  the staff portal logged in as a staff account.
- **Fallback:** if the site is down, play the screen recording of this script (record it at the
  first rehearsal) and narrate over it. If one step fails live, say so and move on to the next tab.

## The script

| Time | Account | What to show | What to say |
|---|---|---|---|
| 0:00 | visitor | **Landing page** (`/`): scroll once to "How it works" and the modules | "A student who arrives finds what the course is, how long it takes and why it is built this way." |
| 0:45 | new | **Home**: the "next up" card, the module list with honest minutes; open **module 0** and answer the queue diagnostic | "Module 0 checks what they need from COS110: a queue, a list, a loop." |
| 2:00 | mid | **Module 3**: the worked trace table, then the trace-table activity: enter one wrong row, show the step's feedback, then fix it | "Feedback says why, for the row that is wrong." |
| 3:15 | mid | **Hints** on a practice question: open hint 1, then 2 | "Four levels, from a nudge to the worked answer; using 3 or 4 is recorded as help." |
| 4:00 | mid | **BFS visualiser** (`Your turn: predict every step`): predict two steps, one wrong | "Prediction before seeing the answer is what makes a visualisation teach." |
| 5:00 | mid | **Module 4**: the Parsons problem, then fill-in: a wrong token, its reason, then right | "Help fades: order the lines, then three blanks, then nine." |
| 6:15 | not-yet | **Mastery report**: objective 6 "Not yet", others met independently or with support | "One result per objective, not one mark." |
| 7:00 | not-yet | **Review path 6**: the new worked example (code and table), practice, fresh items | "A 'not yet' is taught again, then checked on new items." |
| 8:00 | ready | **Report**: "Ready for the lecture"; **badges** page; on a new badge note, **Turn off badges**; the profile picture | "Badges name a skill, and a student can turn them off where they appear." |
| 9:00 | staff | **Staff portal**: the content editor (a module's segments), then the evaluation export | "The designers change content without code; every attempt and hint is exported for evaluation." |
| 9:45 | | Back to the slides' last page: the GitHub link | "The code and both documents are in the repository." |

## Rehearsals (14–15 November)

Two timed run-throughs of the whole slot: 10 minutes of slides, 10 of demo, 5 of questions. Note
each step's time against the table, and cut the narration (not the steps) where it runs over.
Likely questions to prepare answers for:

- Why Python, when COS212 teaches C++ or Java? (The app teaches the algorithm; Python keeps the
  code short enough for Parsons and fill-in, and the trace and the reasoning carry over.)
- Why not run students' code? (A student faked the hidden tests in our sandbox; Parsons and
  fill-in are validated proxies for writing code: Denny et al.)
- How do you know it works? (The pilot plan, the event log, and the delayed post-test we would
  run with real students.)
- Where did you use generative AI, and how did you check it? (ID document §10.)
