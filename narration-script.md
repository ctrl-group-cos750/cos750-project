# Module 2 · A graph in Python — narration script

One narrated screen recording (issue #37). No presenter on camera. Read at a calm pace, about 130 words a minute. Timestamps are approximate; **⏸ CHECKPOINT** marks where the video pauses and the activity appears. The captions file and the transcript use this text word for word.

The graphs are the same campus and shuttle as modules 1 and 3, so the letters, names and edges must stay as they are.

**On screen at the start:** the corner of campus by the Admin block.

```
   A ─── C
   │
   E
```

**Text description (read by screen readers):** Undirected graph with 3 vertices: A is the Admin block; C is the Computer Science building; E is the Engineering building. It has 2 edges: A–C, A–E.

---

## Video — From a picture to a dictionary (≈ 2:30)

Plays after the two recall questions.

| Time | On screen | Narration |
|---|---|---|
| 0:00 | Corner graph | In module 1 you drew graphs as circles and lines. A program can't see a picture, so we need to store the same information as data. |
| 0:15 | Each vertex gets a row: A → C, E | The idea is simple. For every vertex, keep a list of its neighbours. A's neighbours are C and E. C's only neighbour is A. E's only neighbour is A. This is called an **adjacency list**. |
| 0:40 | Code appears: `{"A": ["C", "E"], "C": ["A"], "E": ["A"]}` | In Python, a dictionary does this well. Each key is a vertex, and its value is the list of neighbours. |
| 0:55 | The A–C edge, then "C" in A's list and "A" in C's list highlighted | Notice that the edge between A and C appears twice: C is in A's list, and A is in C's list. That's because you can walk it both ways. |
| 1:05 | **⏸ CHECKPOINT `m2-ck-dict`** | Which dictionary stores this corner of campus? |
| 1:10 | Correct dictionary, with the C list crossed out and redrawn | Right. If you forget one direction, your program can go from A to C but never come back. That bug is easy to make, so keep an eye out for it. |
| 1:25 | Shuttle graph with arrows: A → D → G → A | Now the shuttle from module 1. It only drives one way, so this graph is directed. |
| 1:40 | `{"A": ["D"], "D": ["G"], "G": ["A"]}` | For a directed graph, each arrow is stored once, in the list of the vertex it starts from. From D you can only go to G, so D's list holds just G. |
| 1:55 | **⏸ CHECKPOINT `m2-ck-directed`** | Which dictionary stores the shuttle graph? |
| 2:00 | Class outline: `Graph` with `adjacency`, `add_vertex`, `add_edge` | We'll wrap the dictionary in a small `Graph` class with two methods. `add_vertex` adds a vertex with an empty list. `add_edge` connects two vertices, both ways for an undirected graph, one way for a directed one. |
| 2:20 | "Your turn" card | You'll write both methods yourself. First, a worked example. |

### Notes for whoever records

- Show the dictionary with double quotes, exactly as above, so it matches the activities.
- If a time drifts while recording, update `at_seconds` for that checkpoint in `api/app/seed/module_2/module.json`.
- If the video isn't ready in time, the transcript (this text) works as the text version of the segment.
