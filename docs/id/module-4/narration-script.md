# Module 4 · Build BFS — narration script

One narrated screen recording (issue #37). No presenter on camera. Read at a calm pace, about 130 words a minute. Timestamps are approximate; **⏸ CHECKPOINT** marks where the video pauses and the activity appears. The captions file and the transcript use this text word for word.

The graph is the same campus as modules 1 to 3, and the code is the same `bfs` the activities build, so both must stay as they are.

**On screen throughout:** left, the campus graph with the BFS state panel from module 3 (queue, visited, order); right, the code, with the current line highlighted.

**Text description (read by screen readers):** Undirected graph with 7 vertices: A is the Admin block; B is the Bookshop; C is the Computer Science building; D is the Dining hall; E is the Engineering building; F is the Fountain; G is the Green (sports field). It has 7 edges: A–C, A–E, B–C, B–G, C–F, D–E, E–F.

```python
from collections import deque


def bfs(graph, start):
    visited = {start}
    queue = deque([start])
    order = []
    while queue:
        v = queue.popleft()
        order.append(v)
        for n in sorted(graph.adjacency[v]):
            if n not in visited:
                visited.add(n)
                queue.append(n)
    return order
```

---

## Video — From a trace to code (≈ 2:30)

Plays after the two recall questions.

| Time | On screen | Narration |
|---|---|---|
| 0:00 | Campus graph and state panel, empty code editor | In module 3 you traced BFS by hand. You kept a queue, a visited set and the order. Each of those becomes one line of Python. |
| 0:15 | `from collections import deque` and `queue = deque([start])` appear | For the queue we use `deque` from Python's `collections` module. `append` adds to the back, and `popleft` takes from the front. We start with just the start vertex in it. |
| 0:35 | `visited = {start}` appears; A shown as found | The visited set starts with the start vertex too. It's already in the queue, so it counts as found. |
| 0:50 | `order = []` appears | And an empty list for the order. |
| 1:00 | `while queue:` and the next two lines appear; A moves from the queue to the order | Now the loop. While anything is waiting in the queue, take the vertex at the front and add it to the order. |
| 1:20 | **⏸ CHECKPOINT 1** | Which line takes the vertex at the front of the queue and removes it? |
| 1:25 | `for n in sorted(graph.adjacency[v]):` appears; A's edges to C and E highlighted | Next, look at the vertex's neighbours. `graph.adjacency[v]` is the list from your Graph class in module 2. We sort it, so neighbours are taken in alphabetical order, as in module 3. |
| 1:45 | The `if` and its two lines appear; C and E join the queue and the visited set | If a neighbour isn't in the visited set yet, BFS has just found it. Add it to the set, then to the back of the queue. The set is called visited, but like the found vertices in module 3, a vertex goes in it as it joins the queue, not later when it leaves. |
| 2:05 | **⏸ CHECKPOINT 2** | What could go wrong if we only added vertices to the set when they leave the queue? |
| 2:10 | F shown waiting in the queue while E is processed | Right. A vertex waiting in the queue could be added a second time, just like F in module 3. Marking it as it joins stops that. |
| 2:20 | `return order` appears; the full function and the final order A, C, E, B, F, D, G | When the queue is empty, return the order. That's the whole of BFS: thirteen lines. Now you'll build it yourself in three steps, with a little less help each time. |

### Notes for whoever records

- Show exactly the code above, so it matches the activities.
- The visualiser's Visited panel lists the vertices that have left the queue (module 3's visited). The code's `visited` set holds every vertex found so far, so show it as its own row, labelled "visited set (found)", next to the panel.
- Pause the recording at each checkpoint time; the player pauses there automatically (FR-3.3).
- If a time drifts while recording, set the checkpoint's time in the video editor instead.
- If the video isn't ready in time, the transcript (this text) works as the text version of the segment.

---

## Checkpoint questions (enter these in the video editor)

Videos and their checkpoints are made in the app, not in the fixtures: upload the video in the
staff portal, attach it to its segment in module 4, then add these questions at these times.
In each, **(✓)** marks the right answer, the text after the arrow (→) on a wrong option is its feedback, and the four hints go in the editor's hint ladder.

### Checkpoint 1 (1:20)

`queue` is a `deque`. Which line takes the vertex at the front of the queue and removes it?

- `v = queue.popleft()` **(✓)**
- `v = queue.pop()` → Not quite. pop() takes from the back. Taking the newest item makes it a stack, so the search goes deep instead of wide. Find the method that works on the left (front) end.
- `v = queue[0]` → Not quite. That only looks at the front. queue[0] reads the front item but doesn't remove it, so the loop would never end. Find the method that removes the item as well.

Hints:

1. A queue is first in, first out.
2. New items go on the right with append. So the front is on the left.
3. deque has a method that removes from the left.
4. Answer: `v = queue.popleft()`.

### Checkpoint 2 (2:05)

The code adds a neighbour to the visited set when it joins the queue. What could go wrong if it only added vertices to the set when they leave the queue?

- A vertex could join the queue twice and appear twice in the order. **(✓)**
- BFS would visit the vertices in reverse order. → Not quite. The order of the queue doesn't change. The problem is duplicates: a vertex waiting in the queue can be added a second time. Think back to F waiting in the queue in module 3.
- Nothing. It gives the same result. → Not quite. It goes wrong on graphs with cycles. In a triangle A, B, C, both A and B would add C before C leaves the queue. Try it on a triangle in your head.

Hints:

1. Think about a vertex that is waiting in the queue.
2. Is it in the visited set while it waits?
3. If not, another neighbour can add it to the queue again.
4. Answer: a vertex could join the queue twice and be visited twice.
