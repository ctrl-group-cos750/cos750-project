# Module 1 · What is a graph? — narration script

Two narrated screen recordings on the campus map (issue #37). No presenter on camera. Read at a calm pace, about 130 words a minute. Timestamps are approximate; **⏸ CHECKPOINT** marks where the video pauses and the activity appears. The captions file and the transcript use this text word for word.

The same campus is used again in Module 3 (Meet BFS), so the letters, names and walkways must stay as they are.

**On screen throughout video 1:** the campus map with each building's letter and name.

```
   A ─── C ─── B ─── G
   │     │
   E ─── F
   │
   D
```
A Admin block · B Bookshop · C Computer Science · D Dining hall · E Engineering · F Fountain · G Green

**Text description (read by screen readers):** Undirected graph with 7 vertices: A is the Admin block; B is the Bookshop; C is the Computer Science building; D is the Dining hall; E is the Engineering building; F is the Fountain; G is the Green (sports field). It has 7 edges: A–C, A–E, B–C, B–G, C–F, D–E, E–F.

---

## Video 1 — From a map to a graph (≈ 2:45)

Plays straight after the opening puzzle (`m1-hook`).

| Time | On screen | Narration |
|---|---|---|
| 0:00 | Map, route A → C → B → G highlighted | You just found that the Green is three walkways from the Admin block. To work that out, you ignored almost everything about the campus: the trees, the parking, how big each building is. You only looked at two things: the buildings, and which ones are joined by a walkway. |
| 0:25 | Buildings shrink to circles, walkways to lines | That simpler picture has a name: a **graph**. Each building is a **vertex**. Each walkway is an **edge**. An edge joins two vertices. |
| 0:45 | E highlighted, then A, D, F | Two vertices joined by an edge are **neighbours**. The Engineering building, E, has three neighbours: A, D and F. The Dining hall has just one. |
| 1:00 | Count appears: 7 circles, 7 lines | Let's count. Seven buildings, so seven vertices. Seven walkways, so seven edges. Notice that each walkway counts once, even though it touches two buildings. |
| 1:15 | **⏸ CHECKPOINT `m1-ck-count`** | How many vertices and how many edges does the campus graph have? |
| 1:20 | Title: data structure | Right: seven of each. A graph is a **data structure**. That means it's a way of organising data so a program can use it, just like the queue you met in COS110. |
| 1:40 | Title: algorithm | An **algorithm** is a list of steps that solves a problem. A data structure holds the information; an algorithm works with it. |
| 1:55 | A tour path lights up building by building | One common job is to visit every vertex by following edges, like a tour guide walking to every building on campus. This is called a **graph traversal**. In Module 3 you'll learn BFS, an algorithm for doing it. |
| 2:20 | **⏸ CHECKPOINT `m1-ck-traversal`** | A tour guide walks along walkways until she has visited every building once. In graph terms, what is she doing? |
| 2:25 | Summary card: graph = vertices + edges | So: a graph is a data structure made of vertices and edges. A traversal is an algorithm that visits them. Next, you'll practise reading graphs and build the campus graph yourself. |

---

## Video 2 — One-way or two-way? (≈ 1:45)

Plays after the build activity (`m1-build`).

**On screen:** the shuttle graph. A → D → G → A, drawn with arrows.

**Text description:** Directed graph with 3 vertices: A is the Admin block; D is the Dining hall; G is the Green (sports field). It has 3 edges: A → D, D → G, G → A. Each edge points from the first vertex to the second.

| Time | On screen | Narration |
|---|---|---|
| 0:00 | Campus graph, plain lines | Every walkway on campus can be walked both ways. When the edges of a graph work in both directions, we draw them as plain lines and call the graph **undirected**. |
| 0:20 | Shuttle bus icon; shuttle graph with arrows | The campus shuttle is different. It drives one loop, in one direction only: from the Admin block to the Dining hall, then to the Green, then back to the Admin block. |
| 0:40 | Arrow A → D pulses | To show that, each edge gets an arrow. An edge with an arrow can only be followed the way it points. A graph with arrows is called **directed**. |
| 0:55 | D highlighted, arrow D → G | So from the Dining hall, the shuttle can only take you to the Green. |
| 1:10 | **⏸ CHECKPOINT `m1-ck-oneway`** | Can you ride the shuttle directly from the Dining hall to the Admin block? |
| 1:15 | Path D → G → A highlighted | No. The edge between them points from A to D. To get back to the Admin block, you ride D → G → A. |
| 1:25 | Two people with arrows both ways between them | One last trap. If two people follow each other online, there are two arrows: one each way. The graph is still directed, because each follow is its own one-way edge. |
| 1:40 | Summary card | Plain lines: undirected. Arrows: directed. Next, you'll classify some graphs yourself. |

### Notes for whoever records

- Draw the graph exactly as above, with the letters and names showing, so it matches the activities.
- If a time drifts while recording, update `at_seconds` for that checkpoint in `api/app/seed/module_1/module.json`.
- If the video isn't ready in time, the transcript (this text) works as the text version of the segment.
