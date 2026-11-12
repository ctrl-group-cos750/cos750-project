# Module 5 · Test and debug — narration script

One narrated screen recording (issue #37). No presenter on camera. Read at a calm pace, about 130 words a minute. Timestamps are approximate; **⏸ CHECKPOINT** marks where the video pauses and the activity appears. The captions file and the transcript use this text word for word.

The graph used throughout this video is the same diamond graph used in the worked example and the fix-the-bug activities, so its vertices, edges and labels must stay as they are.

**On screen throughout:** left, the diamond graph with each vertex's letter; right, the BFS code with the current line highlighted.

```
   A ─── B
   │     │
   │     │
   C ─── D
```

**Text description (read by screen readers):** Undirected graph with 4 vertices: A, B, C, D. It has 4 edges: A–B, A–C, B–D, C–D. A connects to B and C; B and C both connect to D, forming a diamond shape. The cycle A–B–D–C–A visits all four vertices. Every edge can be followed in either direction.

---

## Video — Debugging a faulty BFS (≈ 2:45)

Plays at the start of module 5, before the worked example.

### Section 1 — The visited-too-late bug (≈ 1:45)

| Time | On screen | Narration |
|---|---|---|
| 0:00 | Cycle graph, no highlighting | You have written a BFS and tested it on a simple path — a few vertices in a line. It gives the right answer every time. Then you try it on this graph, and something unexpected happens. |
| 0:15 | Faulty code appears on the right | Here is the faulty version. It looks almost right. Spot the difference from the BFS you built in module 4. |
| 0:25 | Line `visited = set()` highlighted; correct `visited = {start}` shown beside it | First difference: visited starts empty. In the correct BFS, visited starts as `{start}`, because the start vertex is already in the queue. |
| 0:40 | Line `visited.add(v)` (after popleft) highlighted | Second difference: visited.add(v) runs just after popleft, not inside the neighbour loop. A vertex is only marked found when it leaves the queue, not when it joins. |
| 0:55 | Graph animates: A dequeues, B and C join queue | Let's trace it. We start at A. A leaves the queue, and A is marked found. Its neighbours are B and C. Neither is in visited yet, so both join the queue. |
| 1:10 | B dequeues; A (visited), D (new) highlighted | B leaves next. A is already found, so we skip it. D is new, so D joins the queue. Queue now: C, D. |
| 1:20 | C dequeues; A (visited), D highlighted with warning arrow | C leaves. A is found. But D? D joined the queue when B was processed. However, visited.add(D) hasn't run yet — D leaves the queue only later. So right now, D is **not** in visited. C adds D to the queue **again**. Queue: D, D. |
| 1:35 | **⏸ CHECKPOINT** | |
| 1:40 | D dequeues twice; output `[A, B, C, D, D]` shown | D is dequeued once, then dequeued a second time. The output is A, B, C, D, D — D visited twice. |
| 1:50 | Two-line fix highlighted side-by-side with the faulty lines | The fix is two changes together. Change `visited = set()` to `visited = {start}`. And move visited.add so it runs inside the neighbour loop, the moment a vertex joins the queue. Now when C checks D, D is already in visited, and D is never queued twice. |

---

### Section 2 — Choosing test cases (≈ 1:00)

| Time | On screen | Narration |
|---|---|---|
| 2:00 | Title card: "Which test cases expose a bug?" | Finding a bug matters, but so does knowing which test case would expose it. Some graphs hide a bug; others bring it right out. |
| 2:10 | Cycle graph shown again | The visited-too-late bug only surfaces when a graph has a **cycle** — a path that leads back to a vertex already in the queue. On a simple path or a tree, every vertex has only one route to it, so it can never be queued twice. |
| 2:20 | Two-islands graph appears: A–B–C on left, D–E on right, no edges crossing | A different bug adds unreachable vertices to the order. This graph has two islands: A, B, C are connected, but D and E are completely cut off. A BFS from A visits only A, B, C. A bug that tacks on every vertex BFS never reached would return A, B, C, D, E — which is wrong. This test exposes the bug because some vertices are unreachable. |

**Text description of the two-islands graph (read by screen readers):** Undirected graph with 5 vertices: A, B, C, D, E. It has 3 edges: A–B, B–C, D–E. Vertices D and E are not connected to A, B or C. Starting BFS from A visits only A, B, C.

| Time | On screen | Narration |
|---|---|---|
| 2:35 | Both graphs side by side with labels | So: choose a **cycle graph** to expose a visited-too-late bug. Choose a **disconnected graph** — one with two separate islands — to expose a bug that adds unreachable vertices. One test cannot do both jobs; that is why you need more than one. |
| 2:45 | "Your turn" card | Now you'll practise both: fixing the bugs and choosing the tests yourself. |

### Notes for whoever records

- Show exactly the faulty and fixed code from the worked example, so it matches activity 504.
- The diamond graph must match activity 506: vertices A, B, C, D; edges A–B, A–C, B–D, C–D.
- The two-islands graph must match activity 507: vertices A, B, C, D, E; edges A–B, B–C, D–E.
- Pause the recording at the checkpoint time; the player pauses there automatically (FR-3.3).
- If a time drifts while recording, set the checkpoint's time in the video editor instead.
- If the video isn't ready in time, the transcript (this text) works as the text version of the segment.

---

## Checkpoint questions (enter these in the video editor)

Videos and their checkpoints are made in the app, not in the fixtures: upload the video in the
staff portal, attach it to its segment in module 5, then add this question at this time.
In each, **(✓)** marks the right answer, the text after the arrow (→) on a wrong option is its feedback, and the four hints go in the editor's hint ladder.

### Checkpoint 1 (1:35)

The faulty BFS is tracing the diamond graph (A–B, A–C, B–D, C–D, start A). B has just dequeued and added D to the queue. Now C dequeues. D is already in the queue but has not left it yet. What does the faulty BFS do with D?

- It adds D to the queue a second time, because D is not in visited yet. **(✓)**
- It skips D, because D is already in the queue. → Not quite. The faulty version only checks visited, not the queue. D is not in visited until it leaves the queue, so nothing stops C from adding it again. Think about when visited.add(D) actually runs.
- It moves D to the front of the queue. → Not quite. BFS never reorders the queue. New vertices only ever join at the back. The question is whether D gets added a second time.

Hints:

1. When does the faulty code add a vertex to visited?
2. The faulty code runs visited.add(v) only after popleft — when the vertex leaves the queue, not when it joins.
3. D is in the queue but hasn't left yet. So when C checks `if D not in visited`, what is the answer?
4. Answer: D is not in visited yet, so C adds it to the queue a second time. D will be dequeued and visited twice.
