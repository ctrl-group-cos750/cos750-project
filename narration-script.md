# Module 4 · Write BFS — narration script

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
| 0:35 | `visited = {start}` appears; A shown as visited | The visited set starts with the start vertex too. It's already in the queue, so it counts as found. |
| 0:50 | `order = []` appears | And an empty list for the order. |
| 1:00 | `while queue:` and the next two lines appear; A moves from the queue to the order | Now the loop. While anything is waiting in the queue, take the vertex at the front and add it to the order. |
| 1:20 | **⏸ CHECKPOINT `m4-ck-popleft`** | Which line takes the vertex at the front of the queue and removes it? |
| 1:25 | `for n in sorted(graph.adjacency[v]):` appears; A's edges to C and E highlighted | Next, look at the vertex's neighbours. `graph.adjacency[v]` is the list from your Graph class in module 2. We sort it, so neighbours are taken in alphabetical order, as in module 3. |
| 1:45 | The `if` and its two lines appear; C and E join the queue and are marked visited | If a neighbour isn't visited yet, mark it visited and add it to the back of the queue. We mark it now, as it joins the queue, not later when it leaves. |
| 2:05 | **⏸ CHECKPOINT `m4-ck-visited`** | What could go wrong if we only marked vertices when they leave the queue? |
| 2:10 | F shown waiting in the queue while E is processed | Right. A vertex waiting in the queue could be added a second time, just like F in module 3. Marking it as it joins stops that. |
| 2:20 | `return order` appears; the full function and the final order A, C, E, B, F, D, G | When the queue is empty, return the order. That's the whole of BFS: fifteen lines. Now you'll build it yourself in three steps, with a little less help each time. |

### Notes for whoever records

- Show exactly the code above, so it matches the activities.
- If a time drifts while recording, update `at_seconds` for that checkpoint in `api/app/seed/module_4/module.json`.
- If the video isn't ready in time, the transcript (this text) works as the text version of the segment.
