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
| 1:35 | **⏸ CHECKPOINT `m3-ck-one-step`** | Let's start the first ring. Which buildings can you reach from A with exactly one walkway? |
| 1:40 | After the checkpoint: C and E highlighted | Right — C and E. In the next video we'll see how BFS keeps track of the rings, using something you already know: a queue. |

---

## Video 2 — BFS step by step on the campus (≈ 4:30)

**On screen:** the visualiser with the graph on the left and the state panel on the right — current vertex, queue, visited set, order so far.

| Time | On screen | Narration |
|---|---|---|
| 0:00 | Visualiser, empty state | To search ring by ring, BFS needs to remember which buildings are waiting to be explored. It uses a **queue** — first in, first out, like the line at the dining hall. |
| 0:15 | Queue: A · Visited: A | We start by putting A in the queue and marking it **visited**. Visited means "already found" — we'll never add it to the queue again. |
| 0:30 | Rules appear as text | BFS repeats three steps until the queue is empty. One: take the vertex at the front of the queue. Two: add it to the order. Three: add each of its neighbours that isn't visited yet to the back of the queue, and mark it visited. We take the neighbours in alphabetical order. |
| 0:50 | Current: A · Queue: C, E · Visited: A, C, E · Order: A | A leaves the queue. Its neighbours are C and E. Neither is visited, so both join the queue and are marked visited. |
| 1:10 | **⏸ CHECKPOINT `m3-ck-who-leaves`** | The queue holds C, then E. Which vertex does BFS take next? |
| 1:15 | Current: C · Order: A, C | C — it joined first, so it leaves first. |
| 1:25 | C's edges highlighted: A, B, F | C's neighbours are A, B and F. Look at the visited set before you answer. |
| 2:05 | **⏸ CHECKPOINT `m3-ck-who-joins`** | Which of C's neighbours join the queue? |
| 2:10 | Queue: E, B, F · Visited: A, B, C, E, F | B and F. A is already visited, so we skip it. Notice that B and F join at the **back**, behind E. |
| 2:25 | Current: E · Order: A, C, E | E is at the front now, so E leaves. Its neighbours are A, D and F. A is visited. D is new. But what about F? F is still waiting in the queue. |
| 2:55 | **⏸ CHECKPOINT `m3-ck-already-queued`** | What should BFS do with F? |
| 3:00 | Queue: B, F, D | F is skipped. We marked it visited when it joined the queue, so it can't be added a second time. Only D joins. This is why we mark vertices visited when they *join* the queue, not when they leave. |
| 3:25 | Current: B · Queue: F, D, G | B leaves. Its new neighbour is G, so G joins the back of the queue. |
| 3:40 | Steps F, D, G play quickly | F, D and G leave in turn. All of their neighbours are already visited, so nothing new joins. The queue is empty, and BFS is finished. |
| 4:00 | Order: A, C, E, B, F, D, G — rings coloured | The order is A, C, E, B, F, D, G. Look at the rings: first A, then the one-walkway buildings C and E, then B, F and D, and finally G. The queue is what keeps the rings in order. |
| 4:20 | "Your turn" card | Now it's your turn. In the visualiser you'll predict every step before it happens. |

### Notes for whoever records

- Record the visualiser itself on staging (prediction mode off), so the video matches what students use next.
- Pause the recording at each checkpoint time; the player pauses there automatically (FR-3.3).
- If a time drifts while recording, update `at_seconds` for that checkpoint in `api/app/seed/module_3/module.json`.
- If the video is not ready in time, the transcript (this text) works as the text version of the segment.
