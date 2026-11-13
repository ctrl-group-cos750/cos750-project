# Writing content: the authoring guide

This folder holds all of Ctrl Academy's course content as JSON files. The API loads them into the
database every time it starts (`python -m app.seed`). This guide is for the instructional design
team: it explains every kind of segment and activity, and how to check your work before you open
a pull request. You do not need to read any Python to use it.

Staff can also edit content in the portal (`/staff/content`). The rules are the same in both
places (SE document NFR-M5, FR-11.3). Portal edits can be exported and committed as fixtures.

## Quick start

1. Copy the template for the kind of activity you want from [`templates/`](templates/).
2. Paste it into the `activities` list of your module's file (`module-3.json` for module 3).
3. Give it a new id, and change the text, the answer, the feedback and the hints.
4. Add an `activity` segment to the module's `segments` list where the student should meet it.
5. Check it: `cd api && .venv/bin/python -m app.seed --check` (see [Check your work](#check-your-work)).

## The files

| File | Holds |
|---|---|
| `objectives.json` | The learning objectives 1 to 7 (ID document Table 1) and the rule that decides "met". |
| `module-0.json` to `module-6.json` | One module each: its details, its segments in order, and its activities. |
| `review.json` | The review path for each objective, and the activities on those paths. |
| `graphs.json` | The graphs the BFS visualiser offers. |
| `templates/` | One example activity per kind. These are **not** loaded: they are only for copying. |
| `demo/` | Demo accounts for testing. Not content. |

Every item has a fixed `id`. Ids never change and are never reused, because students' answers
point at them.

- A module's segments and activities are numbered from 100 times its number: module 3 uses
  301, 302, … and module 0 uses 1, 2, …. Segment ids and activity ids are counted separately.
- Review paths use 1000 + 100 × the objective: objective 5 uses 1501, 1502, ….
- The portal uses ids from 50 000 and the video editor from 100 000. Stay below 50 000.
- Before you pick an id, search the folder for it (`grep -rn '"id": 305' api/app/seed/*.json`).
- To replace a segment, give the new one a new id rather than reusing the old one's. A student's
  saved place follows the segment, not its number: a student on a segment you take out goes back
  to the nearest segment before it that is still there. Next brings them to the new segment only
  if you put it where the old one was; anywhere else, Next takes them to whatever now follows that
  segment. A module whose segments staff have edited in the portal keeps its list (the seed reports
  it as held), so the replacement doesn't reach it: make the change in the portal, or export the
  portal's content and commit it first.

Text is plain, short sentences, in British/South African spelling. Segment bodies and activity
prompts are Markdown, so you can use **bold**, lists and code blocks (` ```python `).

## Modules

A module is one object in the `modules` list of its file:

```json
{
  "id": 1,
  "slug": "what-is-a-graph",
  "title": "What is a graph?",
  "estimated_minutes": 12,
  "goals": [
    "Say what a data structure, an algorithm, a graph and a graph traversal are, with an example of each."
  ],
  "segments": []
}
```

- `slug` is lower case with hyphens, and is unique.
- `estimated_minutes` is 1 to 120.
- `goals` needs at least one goal, written for the student.
- `segments` are the steps of the module, in the order the student meets them (FR-2.2).

## Segment kinds

Every segment has an `id`, a `kind` and a `title` (up to 200 characters). The kinds are:

| Kind | What the student sees | Needs |
|---|---|---|
| `text` | A page of Markdown. | `body` |
| `worked_example` | A worked example in Markdown: the problem solved step by step. | `body` |
| `video` | A narrated video with checkpoint questions. | nothing else (`body` is a note for staff) |
| `activity` | One activity from the `activities` list. | `activity_id` |
| `refresher` | A short refresher on prior knowledge, in module 0 only. | `body`, `refresher_for` |

Any segment may also have `skip_check_activity_id`: if the student answers that activity
correctly, they may skip the segment (a refresher after its diagnostic question, FR-8.1). Skipping
a whole module is the module's quick check instead (activities of purpose `test_out`, FR-8.2).

### Text

```json
{
  "id": 101,
  "kind": "text",
  "title": "The campus map",
  "body": "This is the campus you'll use in this module.\n\nEach line is a walkway, and you can walk every walkway both ways."
}
```

### Worked example

Show the whole method on one problem, one numbered step at a time. Modules 1 to 3 open with
one, and support fades after that (ID document §7.5).

```json
{
  "id": 105,
  "kind": "worked_example",
  "title": "Worked example: reading a graph",
  "body": "Here is how to read any graph. We'll use the campus graph.\n\n**Step 1. List the vertices.** Every circle is a vertex.\n\n**Step 2. List the edges.** Every line is one edge."
}
```

### Video and its checkpoints

The video itself is not in the fixtures, because the MP4 file is uploaded, not committed. You
add a `video` segment as a placeholder. Staff then open the video editor (`/staff/videos`),
upload the MP4 and its captions, write the transcript, attach the video to this segment, and
place checkpoints on the timeline (FR-3.6). Each checkpoint is a multiple choice question, with
a reason for each wrong option and up to four hints, written exactly like the
[multiple choice](#multiple-choice) activity. The student can't skip past a checkpoint until it
is answered correctly (FR-3.5).

```json
{
  "id": 103,
  "kind": "video",
  "title": "From a map to a graph",
  "body": "Staff attach the narrated video to this segment in the video editor, with its checkpoint questions: see `docs/id/module-1/narration-script.md`."
}
```

### Activity

```json
{ "id": 102, "kind": "activity", "title": "Key terms", "activity_id": 101 }
```

Each activity is shown by one segment at most, and only in its own module. Retrieval questions
are never placed in a segment: the module asks them before its first segment (FR-2.4).

### Refresher

Module 0 only. `refresher_for` names the diagnostic topic (`queues`, `python-basics`, `loops`),
and `skip_check_activity_id` is the diagnostic question that lets a student skip it.

```json
{
  "id": 3,
  "kind": "refresher",
  "title": "Refresher: how a queue works",
  "refresher_for": "queues",
  "skip_check_activity_id": 1,
  "body": "A **queue** is **first in, first out** (FIFO): you add to the **back** and take from the **front**."
}
```

## Activities

Every activity has these fields. The `config` is what the student sees; the `solution` stays on
the server and never reaches the browser.

| Field | Meaning |
|---|---|
| `id` | A new, unused number (see the numbering above). |
| `kind` | One of the seven kinds below. |
| `title` | Up to 200 characters. |
| `module_id` | The module it belongs to. Leave it out for an activity on a review path. |
| `objective_id` | The objective (1 to 7) it gives evidence for. |
| `purpose` | What it is for (see below). Defaults to `practice`. |
| `config` | The question, in the kind's shape. |
| `solution` | The answer and the feedback, in the kind's shape. |
| `hints` | Up to four hints, one per level (see below). |

### Purpose and objective tagging

Every activity is tagged with its objective and its purpose (FR-4.3). The seed refuses a
tagging that breaks these rules:

| `purpose` | Use it for | Rules the check enforces |
|---|---|---|
| `practice` | Practice with feedback inside a module. Most activities. | none beyond the basics |
| `diagnostic` | Module 0's quiz on prior knowledge (FR-8.1). | No `objective_id`. |
| `retrieval` | One or two questions at the start of modules 2 to 6, on earlier modules (FR-2.4). | `multiple_choice` only; `module_id` 2 to 6; at most two per module; never placed in a segment. |
| `mastery` | The mastery check (module 6) and the fresh items at the end of a review path. Counts towards the objective's result (FR-7). | Needs `objective_id`; in module 6 or on a review path only. Every objective needs at least one in module 6. |
| `review` | Practice on a review path (ID document §7.6). | Needs `objective_id`; on a review path it needs all four hint levels. |
| `bonus` | Optional bonus quests: points, never mastery (FR-8.3). | none beyond the basics |
| `test_out` | A module's quick check, "Already know this?" (FR-8.2): a student who passes it tests out of the module. It counts for nothing else. | `multiple_choice` only; `module_id` 1 to 5; needs `objective_id`; no hints; never placed in a segment; exactly four per module that has any. |

For example, a practice item for objective 5 in module 3:

```json
"module_id": 3,
"objective_id": 5,
"purpose": "practice",
```

### Feedback: result, reason, next step

Every feedback message has three parts (ID document §7.4):

1. **Result**: is it right? ("Not quite." / "Correct.")
2. **Reason**: why, linked to the concept.
3. **Next step**: what to check, try or review.

For example: "Not quite. `pop` takes the newest vertex from the back, so the queue acts like a
stack. Take the vertex that has waited longest."

Where you write it:

- `solution.feedback`: one message per wrong answer (per wrong option, left item, blank and
  token, faulty line or test case, depending on the kind). A wrong answer with no message gets a
  generic one, so write one for every wrong answer you can foresee, especially the ones built
  from a misconception (ID document §2.5).
- `solution.explanation`: shown instead of the plain "Correct." when the answer is right,
  saying why it is right (FR-4.2). Every module practice item needs one (a test checks it); a
  trace's solution holds only this, because the engine works out its answer. Mastery-check items
  must not have one yet.
- Parsons problems and trace tables have no `feedback` field: the checker marks each misplaced
  line or wrong row itself. Put the reasoning in the hints and the explanation.

### The four hint levels

Hints are shown one at a time, only when the student asks (ID document §7.5). Give all four:

| Level | What it does | Example |
|---|---|---|
| 1 | Nudge: the key idea. | "Which vertex has been in the queue the longest?" |
| 2 | Targeted hint: the exact step or line. | "Look at where a vertex is added to the found set." |
| 3 | Partial solution: part of the answer. | "Row 1: A leaves, and B and C join." |
| 4 | Worked solution: the full answer, explained. | "Answer: the order is A, B, C, D. …" |

```json
"hints": [
  { "level": 1, "body": "A queue is first in, first out." },
  { "level": 2, "body": "Blank 1 takes a vertex from the front of the queue." },
  { "level": 3, "body": "Blank 1 is popleft." },
  { "level": 4, "body": "Answer: blank 1 is popleft, and blank 2 is not in. …" }
]
```

Using level 3 or 4 marks a later correct answer as "met with support" (FR-4.5), and the student
is warned before level 3. Each level appears once.

## Activity kinds

There are seven kinds. Each has a complete, valid template in `templates/<kind>.json`. The
examples below show only `config` and `solution`; open the template for the whole activity.

### Multiple choice

`templates/multiple_choice.json`. Pick one option.

```json
"config": {
  "prompt": "Which of these problems is BFS a good fit for?",
  "options": [
    { "id": "a", "label": "Finding the route from the Admin block to the Green that uses the fewest walkways." },
    { "id": "b", "label": "Sorting a list of test marks from highest to lowest." },
    { "id": "c", "label": "Adding up the marks in a list." }
  ]
},
"solution": {
  "correct": "a",
  "explanation": "Correct. BFS visits the vertices closest to the start first, so it finds the route with the fewest walkways. Next, try tracing it on the campus graph.",
  "feedback": {
    "b": "Not quite. Sorting a list is a job for a sorting algorithm, and a list has no edges to follow. BFS traverses a graph. Look for the option that has vertices joined by edges.",
    "c": "Not quite. Adding up a list needs one loop, not a graph. BFS traverses a graph by following its edges. Look for the option that has vertices joined by edges."
  }
}
```

- 2 to 10 options, each with a unique `id`. They are shown in the order written, so don't
  always put the right answer first.
- `correct` is one option id. `feedback` is keyed by the wrong options' ids.

### Matching

`templates/matching.json`. Pair each item on the left with one on the right.

```json
"config": {
  "prompt": "Match each situation to the kind of graph that models it.",
  "left": [
    { "id": "s1", "label": "Walkways you can walk both ways" },
    { "id": "s2", "label": "One-way streets" }
  ],
  "right": [
    { "id": "u", "label": "Undirected graph: each edge goes both ways" },
    { "id": "d", "label": "Directed graph: each edge goes one way" }
  ]
},
"solution": {
  "pairs": { "s1": "u", "s2": "d" },
  "explanation": "Correct. When a link works both ways, the graph is undirected. …",
  "feedback": {
    "s1": "Not quite. You can walk a walkway both ways, so its edge has no direction. Ask: does the link work both ways?",
    "s2": "Not quite. A one-way street can only be driven one way, so its edge needs an arrow. Ask: does the link work both ways?"
  }
}
```

- Up to 20 left items and 30 right items. `right` may have extra choices, and one right item
  may fit several left items.
- `pairs` pairs every left item, and only those. `feedback` is keyed by left item id.

### Parsons problem

`templates/parsons.json`. Put shuffled lines of code in order (FR-5.4).

```json
"config": {
  "lines": [
    { "id": 4, "text": "    graph.adjacency[u].append(v)" },
    { "id": 2, "text": "    graph.add_vertex(u)" },
    { "id": 6, "text": "    graph.adjacency[u] = [v]" },
    { "id": 1, "text": "def add_edge(graph, u, v):" },
    { "id": 5, "text": "    graph.adjacency[v].append(u)" },
    { "id": 3, "text": "    graph.add_vertex(v)" }
  ]
},
"solution": {
  "order": [1, [2, 3], [4, 5]],
  "alternatives": [[1, 2, 4, 3, 5], [1, 3, 5, 2, 4]],
  "explanation": "Correct. Both vertices must exist before an edge is added, and an undirected edge is stored in both vertices' lists."
}
```

- Write `lines` in the shuffled order the student sees. Keep the indentation in `text`.
- `order` is one correct order of line ids. A line left out of it (here 6) is a distractor.
- **Interchangeable lines:** a group in square brackets, such as `[2, 3]`, may go in any order
  among itself. Use it for lines that can swap, like BFS's three starting values
  (`[3, 4, 5]`) or `found.add(n)` and `queue.append(n)`.
- **Alternatives:** `alternatives` lists other correct orders, written the same way, for a line
  that can move further than a swap with its neighbour. Each must use exactly the same lines as
  `order`.
- The check refuses an unknown line id, a line used twice, a group of fewer than two lines, and
  an alternative that `order` (or another alternative) already accepts.

### Fill in the blanks

`templates/fill_in.json`. Choose a token for each blank in the code.

```json
"config": {
  "code": "def bfs(graph, start):\n    …\n        v = queue.__1__()\n        …\n            if n __2__ found:\n    …",
  "blanks": [1, 2],
  "options": ["popleft", "pop", "not in", "in"]
},
"solution": {
  "answers": { "1": "popleft", "2": "not in" },
  "explanation": "Correct. popleft takes the vertex that has waited longest, and not in skips a vertex that has already been found.",
  "feedback": {
    "1": { "pop": "Not quite. pop takes the newest vertex from the back, so the queue acts like a stack and the order is no longer BFS. Take the vertex that has waited longest." },
    "2": { "in": "Not quite. With in, only vertices already found are added again, and new ones are never found. Add a neighbour only if it has not been found yet." }
  }
}
```

- Mark each blank in `code` as `__1__`, `__2__`, … and list the numbers in `blanks`.
- `options` is the one list of tokens offered for every blank. Each answer must be one of them.
- `feedback` is keyed by blank, then by wrong token. Never give feedback for the right token.

### Trace table

`templates/trace.json`. Fill in the BFS trace, one row each time a vertex leaves the queue:
the vertex, the queue after the step, the visited set (the vertices that have left the queue) and
the order so far (FR-4.1, FR-6.6). Modules 4 to 6 call the set of vertices that have joined the
queue `found`, so "visited" means one thing everywhere.

```json
"config": {
  "directed": false,
  "vertices": ["A", "B", "C", "D"],
  "edges": [
    { "source": "A", "target": "B" },
    { "source": "A", "target": "C" },
    { "source": "B", "target": "D" },
    { "source": "C", "target": "D" }
  ],
  "start_vertex": "A"
},
"solution": {
  "explanation": "A finds B and C. When C leaves, D is already waiting, so it isn't added again."
}
```

- You give only the graph. The answer is worked out by the app's BFS engine, so `solution`
  holds no answer, only the `explanation` (or nothing: `{}`). Neighbours are visited in
  alphabetical order.
- Up to 50 vertices; the check refuses an edge to an unknown vertex or an unknown start.
- Work the trace out yourself for hints 3 and 4.

### Fix the bug

`templates/fix_the_bug.json`. The student rebuilds a faulty BFS: they replace each faulty line
with a correction and move any line that is in the wrong place (FR-5.5, objective 7).

```json
"config": {
  "prompt": "This BFS visits the vertices in the wrong order. Replace the faulty line with a correction.",
  "lines": [
    { "id": 1, "text": "from collections import deque" },
    { "id": 2, "text": "def bfs(graph, start):" },
    { "id": 3, "text": "    found = {start}" },
    { "id": 4, "text": "    queue = deque([start])" },
    { "id": 5, "text": "    order = []" },
    { "id": 6, "text": "    while queue:" },
    { "id": 7, "text": "        v = queue.pop()" },
    { "id": 8, "text": "        order.append(v)" },
    { "id": 9, "text": "        for n in sorted(graph.adjacency[v]):" },
    { "id": 10, "text": "            if n not in found:" },
    { "id": 11, "text": "                found.add(n)" },
    { "id": 12, "text": "                queue.append(n)" },
    { "id": 13, "text": "    return order" }
  ],
  "corrections": [
    { "id": 21, "text": "        v = queue[0]" },
    { "id": 20, "text": "        v = queue.popleft()" }
  ]
},
"solution": {
  "order": [1, 2, [3, 4, 5], 6, 20, 8, 9, 10, [11, 12], 13],
  "explanation": "Correct. popleft takes the vertex that has waited longest, so BFS visits the closest vertices first.",
  "feedback": {
    "7": "Not quite. pop takes the newest vertex from the back, so the queue acts like a stack and BFS goes deep first. Replace it with a line that takes the vertex at the front."
  }
}
```

- `lines` is the faulty program in its faulty order. `corrections` are the lines the student
  may swap in; include a wrong correction or two (here 21).
- Line ids and correction ids share one numbering, so they must all differ.
- `order` is the fixed program, written like a Parsons `order`, with groups and
  `alternatives` allowed. It must differ from the faulty program.
- `feedback` is keyed by the id of each faulty line: why that line is wrong.

### Choose the tests

`templates/choose_tests.json`. The student picks the test cases that the faulty BFS fails
(FR-5.5, objective 7).

```json
"config": {
  "prompt": "This BFS has a bug. Choose every test case it fails: each one is a graph, a start vertex and the order a correct BFS visits it in.",
  "code": "from collections import deque\n\n\ndef bfs(graph, start):\n    …\n        v = queue.pop()\n    …",
  "tests": [
    {
      "id": "fork",
      "directed": false,
      "vertices": ["A", "B", "C"],
      "edges": [{ "source": "A", "target": "B" }, { "source": "A", "target": "C" }],
      "start_vertex": "A",
      "expected": ["A", "B", "C"]
    },
    {
      "id": "line",
      "directed": false,
      "vertices": ["A", "B", "C"],
      "edges": [{ "source": "A", "target": "B" }, { "source": "B", "target": "C" }],
      "start_vertex": "A",
      "expected": ["A", "B", "C"]
    }
  ]
},
"solution": {
  "exposing": ["fork"],
  "explanation": "Correct. The bug only shows when a vertex has two or more new neighbours, because then pop takes the wrong one first.",
  "feedback": {
    "fork": "A has two neighbours, so pop takes C before B: the faulty version visits A, C, B and fails this test.",
    "line": "Each vertex has only one new neighbour, so the queue never holds two vertices: the faulty version passes this test."
  }
}
```

- 2 to 8 test cases (4 to 6 is the design, FR-5.5), each with a unique `id`.
- `expected` is the order a **correct** BFS visits. The check runs the BFS engine on every test
  and refuses one whose `expected` is wrong.
- `exposing` lists the tests the faulty code fails. At least one, and not all of them.
- `feedback` is keyed by test id: why that test does, or doesn't, expose the bug.

### Kinds not available yet

FR-4.1 also lists labelling a diagram, classifying graphs, building a graph and predicting the
next BFS vertex. These have no checker yet, so the check refuses them. Until they do, write a
prediction as a multiple choice question ("Which vertex does BFS visit next?") and a
classification as matching.

## Review paths (`review.json`)

When the mastery check marks an objective "Not yet", the student opens that objective's review
path (FR-7.5, ID document §7.6). Each objective has exactly one:

```json
{
  "objective_id": 1,
  "segments": [
    { "id": 1101, "kind": "worked_example", "title": "Review: data structures, algorithms, graphs and traversals", "body": "…" },
    { "id": 1102, "kind": "activity", "title": "Review practice", "activity_id": 1101 },
    { "id": 1103, "kind": "activity", "title": "Objective 1 · fresh item 1 of 5", "activity_id": 1102 }
  ]
}
```

- It starts by teaching the objective again (a `worked_example` or `text`), never with an
  activity, and has no refresher and no skip checks.
- Then practice: activities with `purpose` `review` and all four hint levels.
- Then fresh items: activities with `purpose` `mastery`. All the practice comes first.
- Its activities have no `module_id` and have this path's `objective_id`. They go in the
  `activities` list of `review.json`, numbered 1000 + 100 × the objective.

## Objectives (`objectives.json`)

```json
{
  "id": 5,
  "bloom_level": "Apply",
  "text": "Trace BFS manually on a given graph, correctly identifying the next vertex to process, the queue contents, the visited vertices and the traversal order.",
  "criterion": "Correct queue, visited set and next vertex at every step, with at most one error.",
  "max_wrong": 1
}
```

`criterion` is the wording from ID document Table 1. The rule the app counts is either
`pass_fraction` ("at least 4 of 5 right" is `0.8`) or `max_wrong` ("at most one error" is `1`),
never both. Ids run 1 to 8, because each objective has a badge.

## Graphs (`graphs.json`)

The scenarios the BFS visualiser offers (FR-6.1):

```json
{
  "id": 1,
  "name": "Six towns (undirected)",
  "directed": false,
  "vertices": ["A", "B", "C", "D", "E", "F"],
  "edges": [{ "source": "A", "target": "C" }, { "source": "A", "target": "B" }],
  "start_vertex": "A"
}
```

Up to 50 vertices. The check runs BFS on each graph, so an unknown start or an edge to a
missing vertex is refused.

## Check your work

One command checks every fixture file and every template with the same rules CI applies
(the `test_every_committed_fixture_is_valid` and `tests/test_templates.py` tests), without
touching a database:

```
cd api
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # once
.venv/bin/python -m app.seed --check
```

It prints `seed --check: fixtures valid (…); templates valid (…)`, or `FAILED` with the file,
the item and what is wrong. For example, a multiple choice answer that is not one of its options
gives:

```
seed --check: FAILED
module-0.json: 1 validation error for FixtureFile
activities.0
  Value error, activity 1: correct option 'z' is not one of the options [...]
```

Fix that and run it again. `activities.0` is the first activity in the file, counting from 0.

CI also runs the module tests (`tests/test_module_*.py`), which check that a module's content
agrees with the BFS engine (for example, that a trace table's last hint is the engine's answer).
To run everything CI runs before you push, use `scripts/check.sh` from the repository root.

## Adding a template

If a new activity kind gets a checker (`app/services/content.py`), add
`templates/<kind>.json` and a section above. `tests/test_templates.py` fails until every kind
has a template that validates.
