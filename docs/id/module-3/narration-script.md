# Module 3 · Meet BFS — narration script

Two narrated screen recordings of the BFS visualiser on the campus graph. No presenter on camera (SE §15.3, decision 4). Read at a calm pace, about 130 words a minute. Timestamps are approximate; **⏸ CHECKPOINT** marks where the video pauses and the activity appears. The captions file and the transcript use this text word for word.

**On screen throughout:** the campus graph with each building's letter and name.

```
   A ─── C ─── B ─── G
   │     │
   E ─── F
   │
   D
```
A Admin block · B Bookshop · C Computer Science · D Dining hall · E Engineering · F Fountain · G Green

---

## Video 1 — Why BFS? The fewest walkways (≈ 2:00)

| Time | On screen | Narration |
|---|---|---|
| 0:00 | Campus graph, A highlighted, G highlighted | It's your first day on campus. You're at the Admin block, A, and your friends are waiting at the Green, G. You want the route with the fewest walkways. How would you find it? |
| 0:20 | Graph only | Each building is a vertex, and each walkway is an edge. The walkways go both ways, so this is an undirected graph — just like in module 1. |
| 0:35 | Ring 1 (around C and E) fades in | One way to search is in rings. First, every building one walkway from A. |
| 0:50 | Ring 2 (B, F, D) fades in | Then every building two walkways away. Then three. The first time you reach G, you know you've used the fewest walkways possible. |
| 1:05 | Title: Breadth-first search | Searching ring by ring like this is called **breadth-first search**, or BFS. "Breadth-first" means we go wide before we go deep: we finish one ring before we start the next. |
| 1:20 | Graph, A highlighted | BFS is useful whenever you care about the fewest steps: fewest stops on a train map, friends of friends on a social network, or the fewest moves in a puzzle. |
| 1:35 | **⏸ CHECKPOINT 1** | Let's start the first ring. Which buildings can you reach from A with exactly one walkway? |
| 1:40 | After the checkpoint: C and E highlighted | Right — C and E. In the next video we'll see how BFS keeps track of the rings, using something you already know: a queue. |

---

## Video 2 — BFS step by step on the campus (≈ 4:30)

**On screen:** the visualiser with the graph on the left and the state panel on the right — current vertex, queue, visited, order so far.

**Words used (they match the visualiser and the trace table):** a vertex is **found** when it joins the queue, and BFS never adds a vertex it has already found. It is **visited** when it leaves the queue, which is when it joins the order.

| Time | On screen | Narration |
|---|---|---|
| 0:00 | Visualiser, empty state | To search ring by ring, BFS needs to remember which buildings are waiting to be explored. It uses a **queue** — first in, first out, like the line at the dining hall. |
| 0:15 | Queue: A · Visited: – | We start by putting A in the queue. A is now **found**: BFS will never add it to the queue again. |
| 0:30 | Rules appear as text | BFS repeats three steps until the queue is empty. One: take the vertex at the front of the queue. It is now **visited**. Two: add it to the order. Three: add each of its neighbours that hasn't been found yet to the back of the queue. We take the neighbours in alphabetical order. |
| 0:50 | Current: A · Queue: C, E · Visited: A · Order: A | A leaves the queue, so A is visited. Its neighbours are C and E. Neither has been found yet, so both join the queue. |
| 1:10 | **⏸ CHECKPOINT 2** | The queue holds C, then E. Which vertex does BFS take next? |
| 1:15 | Current: C · Order: A, C | C — it joined first, so it leaves first. |
| 1:25 | C's edges highlighted: A, B, F | C's neighbours are A, B and F. Which of them has BFS already found? |
| 2:05 | **⏸ CHECKPOINT 3** | Which of C's neighbours join the queue? |
| 2:10 | Queue: E, B, F · Visited: A, C | B and F. A has already been found, so we skip it. Notice that B and F join at the **back**, behind E. |
| 2:25 | Current: E · Order: A, C, E | E is at the front now, so E leaves. Its neighbours are A, D and F. A is visited. D is new. But what about F? F hasn't been visited yet: it is still waiting in the queue. |
| 2:55 | **⏸ CHECKPOINT 4** | What should BFS do with F? |
| 3:00 | Queue: B, F, D | F is skipped. It was found when it joined the queue, so it can't be added a second time, even though it hasn't been visited yet. Only D joins. That is why BFS checks whether a vertex has been *found*, not only whether it has been visited. |
| 3:25 | Current: B · Queue: F, D, G | B leaves. Its new neighbour is G, so G joins the back of the queue. |
| 3:40 | Steps F, D, G play quickly | F, D and G leave in turn. All of their neighbours have already been found, so nothing new joins. The queue is empty, and BFS is finished. |
| 4:00 | Order: A, C, E, B, F, D, G — rings coloured | The order is A, C, E, B, F, D, G. Look at the rings: first A, then the one-walkway buildings C and E, then B, F and D, and finally G. The queue is what keeps the rings in order. |
| 4:20 | "Your turn" card | Now it's your turn. In the visualiser you'll predict every step before it happens. |

### Notes for whoever records

- Record the visualiser itself on staging (prediction mode off), so the video matches what students use next.
- Pause the recording at each checkpoint time; the player pauses there automatically (FR-3.3).
- If a time drifts while recording, set the checkpoint's time in the video editor instead.
- If the video is not ready in time, the transcript (this text) works as the text version of the segment.

---

## Checkpoint questions (enter these in the video editor)

Videos and their checkpoints are made in the app, not in the fixtures: upload each video in the
staff portal, attach it to its segment in module 3, then add these questions at these times.
In each, **(✓)** marks the right answer, the text after a wrong option is its feedback, and the four hints go in the editor's hint ladder.

### Video 1, checkpoint 1 (1:35)

You start at the Admin block (A). Which buildings can you reach by walking along exactly **one** walkway?

- C and E **(✓)**
- B and C: B is not joined to A. Count only the walkways that touch A.
- C, E and F: F needs two walkways (A to C, then C to F).
- Only C: Look again: A has two walkways, one to C and one to E.

Hints:

1. Find vertex A on the map.
2. Count the edges that touch A. Each one leads to a building one step away.
3. A has two edges.
4. Answer: C and E. They are A's neighbours.

### Video 2, checkpoint 2 (1:10)

A has been visited. The queue now holds **C, E** (front first). Which vertex does BFS take next?

- C **(✓)**
- E: E joined after C. A queue is first in, first out.
- B: B hasn't been found yet. BFS only takes the vertex at the front of the queue.

Hints:

1. BFS always takes the next vertex from the queue.
2. A queue is first in, first out, like a line at the dining hall.
3. Which of C and E joined the queue first?
4. Answer: C. It is at the front of the queue.

### Video 2, checkpoint 3 (2:05)

BFS is now visiting **C**. C's neighbours are A, B and F. Found so far: A, C and E. Which vertices join the queue?

- B and F **(✓)**
- A, B and F: A has already been found. Adding it again would visit it twice.
- Only B: F is a neighbour of C too, and it hasn't been found yet.
- B, F and G: G is not a neighbour of C. Only C's own edges count.

Hints:

1. Only neighbours of the vertex being visited can join the queue.
2. Skip any neighbour BFS has already found.
3. C's neighbours are A, B and F. Which of them has been found?
4. Answer: B and F. A is skipped because it has already been found.

### Video 2, checkpoint 4 (2:55)

BFS is visiting **E**. Its neighbours are A, D and F. The queue holds B, F: F has been found but not visited yet. What happens to F?

- Nothing. F has already been found, so it is skipped. **(✓)**
- F joins the back of the queue again: then F would be visited twice. That is the mistake BFS avoids by remembering what it has found.
- F moves to the front of the queue: BFS never reorders the queue. New vertices only join at the back.

Hints:

1. Has BFS found F already?
2. A vertex is found the moment it joins the queue.
3. BFS skips every neighbour it has already found, visited or not.
4. Answer: F is skipped. Only D joins the queue at this step.
