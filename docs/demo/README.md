# Demo script (#82)

The examination slot is 30 minutes: at most 10 for the presentation, at most 10 for the demonstration, 5 for questions and 5 to set up and leave. The spec asks the presentation and demo for "an overview of your educational design decisions and a live demonstration of your prototype". So the demo shows **how the app teaches**: each step names the instructional decision behind it, and where the ID document argues it. It is not a tour of the code. The SE side belongs in the presentation, in a sentence.

The story is one student's journey, from never having heard of a graph to "ready for the lecture", told with the four demo accounts. The plan runs **8 min 45 s**, which leaves a 75-second buffer.

## Before the slot

- [ ] **The production deploy is frozen** after the last staging → master merge. Per #82, nothing is merged or deployed after the first rehearsal.
- [ ] **Re-seed production 15 minutes before the slot,** so the demo accounts are back at their stages: rehearsals change them. On Coolify, restart the api container (the seed runs on every start), or run `python -m app.seed` in its terminal. That restores the demo accounts and changes no code.
- [ ] **Open each account in its own browser profile or private window,** because one browser holds one session:

  | Window | Account | Opens on |
  |---|---|---|
  | 1 | `new@demo.example.com` | the module map |
  | 2 | `mid@demo.example.com` | module 1, then module 3 |
  | 3 | `not-yet@demo.example.com` | module 4, then the mastery report |
  | 4 | `ready@demo.example.com` | the badges page |

  All four share the `DEMO_PASSWORD` set on Coolify.
- [ ] **Screen:** browser zoom at 125%, light mode, notifications off, and the presenter's notes on a second screen.
- [ ] **Fallbacks ready:** staging, with the same accounts, in a fifth window, and the screen recording from rehearsal 1 on the laptop's desktop. See [If something fails](#if-something-fails).
- [ ] **Check which features are deployed.** Some steps depend on open PRs; the script marks them **(if deployed)**:
  - narrated videos (#37);
  - restored answers (#195);
  - bonus quests (#196).

## Roles

- **Driver:** one person at the keyboard, who doesn't talk.
- **Narrator:** one person per step, from the ID team where possible; fill the names in at rehearsal 1.
- **Timekeeper:** shows the minute cards (3, 6, 8, 9).

## The script

| Time | Window | What the driver does | What the narrator says: the decision, and the theory |
|---|---|---|---|
| **0:00–0:30** Intro | 1 | Shows the module map. | "This is a pre-lecture app for COS212: graphs and breadth-first search, for students who have never seen either. Every screen you'll see is an instructional decision, and we'll name it as we go." *(ID §1: purpose, and why graphs and BFS.)* |
| **0:30–1:30** First contact | 1, new | Points at the minutes line and the module states. Opens **module 0**: the opening puzzle, the "By the end of this module you can…" box, then the first diagnostic question. | "The course is seven short modules. Locked modules open in order, so the path is guided: novices do worse when left to discover alone. The module opens with a **puzzle before any terms**, Gagné's event 1 (gain attention), then states its **objectives in plain words**, event 2. The diagnostic checks the COS110 queue knowledge BFS builds on, event 3, so we **activate prior knowledge** before teaching on top of it." *(ID §4, Gagné table; §2 prior knowledge; §5 prior knowledge and retrieval.)* |
| **1:30–3:00** Feedback and hints | 2, mid | Opens **module 1 → "Label the bus-stop graph"** (104). Picks one road for a stop, and checks. Shows the "Your graph \| Bus map" tabs. Opens hints 1 and 2, then clicks hint 3 to show the warning. Then answers correctly. | "A wrong answer gets **three-part feedback**: what's wrong, why, and what to check next. That's Hattie and Timperley's three feedback questions. For graph questions, the student also sees **their own answer drawn as a graph** beside the map, so they compare it with the situation side by side: Mayer's spatial contiguity. **Hints come as a ladder**: two nudges, then a warning that hints 3 and 4 give a lot away and count as 'met with support'. That's scaffolding in the zone of proximal development, and the student chooses how much help to take. A right answer says *why* it's right, too." *(ID §7.4 feedback; §7.5 hint ladder; §5 scaffolding and ZPD.)* **(If deployed, #195:)** go back with Previous: "the answer is still there." |
| **3:00–4:45** BFS by doing | 2, mid | Opens **module 3**. Scrolls the BFS lesson segment ("BFS step by step"): the video with its checkpoint pause **(if a video is deployed)**, or its text version. Opens **"Your turn: predict every step"** → visualiser in **Prediction mode**: predicts one vertex right and one wrong. Back in module 3, opens the **trace table**, and points at its columns. | "BFS is taught **one idea per segment**, with the graph, queue and visited set side by side, to keep extraneous load down (Mayer's multimedia principles). Then the student must **predict** the next vertex before the visualiser shows it. How students use a visualisation matters more than what it shows (Hundhausen, Douglas and Stasko; Naps and colleagues), so the student is active, not watching. Then they **trace by hand**: novices need to trace code before they can write it (Lister and colleagues). And they can't click past a practice item: Next waits for a right answer, or for the last hint. That's mastery learning, and it stops gaming the system." *(ID §5 active learning; cognitive load and multimedia design; prior knowledge, retrieval and tracing; §4 lesson sequence.)* |
| **4:45–5:45** From reading to writing code | 3, not-yet | Opens **module 4**: the worked example with its subgoal labels, then the **Parsons problem** (moves a line with the keyboard), then a **fill-in** activity. | "Writing BFS is **faded**: a full worked example labelled with its subgoals, then a Parsons problem where the student orders given lines, then completion with missing tokens. Each step removes some support: Renkl and Atkinson's fading, and Parsons problems as the step between reading and writing code (Denny and colleagues). Everything works by keyboard, without dragging, which is UDL's multiple means of action." *(ID §5 scaffolding; §4 lesson sequence; §6 UDL and accessibility.)* |
| **5:45–7:15** Assessment and the second chance | 3, not-yet | Opens the **Report**. Points at the three states and the "To meet it" criteria. On objective 6 ("not yet"), clicks **Start review path**: the new worked example, then practice of the same kind as the mastery item. | "Module 6 is the **mastery check**: unseen items, one answer each, no right or wrong until the end, at most two hints. It's **summative**, so it has to measure the student, not the hints. The report is **criterion-referenced**: each objective is met independently, met with support, or not yet, against the criterion in our objectives table, never against other students. 'Not yet' leads to a **review path** that re-teaches with a new worked example and new practice: Bloom's mastery learning, with corrective help before the lecture rather than a mark." *(ID §3 objectives and success criteria; §7 assessment plan, criterion-referenced; §7.6 review path.)* |
| **7:15–8:15** Motivation | 4, ready | Shows **"Ready for the lecture"**, then the **badges page**: gold and bronze objective badges, milestones, and the **Hide points and badges** switch. **(If deployed, #196:)** the bonus quest badges. | "Motivation follows **ARCS**: relevance from campus examples, confidence from the hint ladder and the second chance, satisfaction from visible progress. Badges name **a skill the student now has**, never time or clicks. They're **private**, with no leaderboard, because many of our students are driven by fear of failure, and the student can hide them: autonomy, in Self-Determination Theory. Bronze means met with support and gold met independently, so the reward matches the assessment. **Bonus quests** give a strong student extra challenge without touching their results." *(ID §7 motivation, ARCS table, flow, Malone and Lepper; engagement and gamification.)* |
| **8:15–8:45** Close | 4 | Back to the map. | "Our evaluation so far is **formative**: an expert review of the interface against Nielsen's heuristics, accessibility checks of every page, and every answer checked automatically. The team pilot (think-aloud, SUS and ARCS questions) **[has run / runs this weekend: update at rehearsal 2]**. A delayed post-test with real COS212 students is the next step, because we who built it can't tell you whether it teaches. Over to questions." *(ID §8 evaluation: formative evaluation so far, pilot, limitations.)* |

If the timekeeper shows **8** before the badges step starts, skip the bonus quests and go straight to the close.

## If something fails

| Problem | What to do |
|---|---|
| Production won't load | Switch to window 5 (staging, same accounts) and carry on. Say once: "we'll use our staging copy". |
| Both are down | Play the rehearsal-1 screen recording, and narrate over it with the same script. |
| An account is in the wrong state (a rehearsal changed it) | Re-seed (see the checklist). If there's no time: for the report and review path use `not-yet`, and for "ready" use `ready`. Both are fixed by the seed, not by what was clicked. |
| A video isn't uploaded | Use the segment's text version (#175) and say: "the narrated video slots in here; the text is its script". |
| The visualiser is slow | Use **Watch mode** for one step, and describe prediction in words. |

## Questions to expect

Short answers, each pointing to where the ID document argues it:

| Question | Answer | Where |
|---|---|---|
| Why graphs and BFS? | CS2023 core (AL-Foundational), a known source of misconceptions, and it builds on the queue from COS110. | ID §1, §2 |
| Which learning theories, and where in the app? | Constructivism (prediction, tracing), cognitive load (one idea per segment, worked examples), scaffolding and ZPD (hint ladder, fading), retrieval practice (recall questions at module starts), mastery learning (review path). | ID §5 |
| How do you cater for learning styles? | We don't match content to a "style": the evidence doesn't support it (Pashler and colleagues). Instead we follow UDL: several representations of everything (text, worked examples, the visualiser, code), several ways to act, and several sources of motivation. | ID §6 |
| How do you keep students motivated? | ARCS, with SDT for autonomy, competence and relatedness, and private, skill-named badges. No streaks or leaderboards. | ID §7 |
| How do you know the scaffolding helps and doesn't just give answers away? | Hints 3 and 4 mark a result "with support", the mastery check caps hints at 2 and withholds right or wrong, and a practice item needs a real answer to move on. | ID §7.3–7.5 |
| How would you show it works? | Kirkpatrick levels 1 and 2: the pilot survey (SUS, ARCS) for reaction, and the mastery check against a delayed post-test without hints, with effect sizes. Seven team members are too few for a stable SUS. | ID §8 |
| It's longer than 75 minutes, isn't it? | Yes. As written it's about 165 minutes. The pilot timings show where; the next step is to cut or make content optional, rather than rush students through it. | ID §4 lesson sequence note, §9 |
| Where did you use generative AI? | For drafting content and tooling. Every prompt is in ID §10, and the team checked and edited all output. | ID §10 |
| What would you do differently? | Get learners in front of it earlier; our pilot was team members only. | ID §9 |

## Rehearsals

| | Date | Total time | What went wrong | Changed |
|---|---|---|---|---|
| 1 | 14 Nov | | | |
| 2 | 15 Nov | | | |

After rehearsal 1, record the whole demo on production (the fallback), then re-seed.
