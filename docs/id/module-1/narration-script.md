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

Plays straight after the opening puzzle, "Puzzle: the fewest walkways".

| Time | On screen | Narration |
|---|---|---|
| 0:00 | Map, route A → C → B → G highlighted | You just found that the Green is three walkways from the Admin block. To work that out, you ignored almost everything about the campus: the trees, the parking, how big each building is. You only looked at two things: the buildings, and which ones are joined by a walkway. |
| 0:25 | Buildings shrink to circles, walkways to lines | That simpler picture has a name: a **graph**. Each building is a **vertex**. Each walkway is an **edge**. An edge joins two vertices. |
| 0:45 | E highlighted, then A, D, F | Two vertices joined by an edge are **neighbours**. The Engineering building, E, has three neighbours: A, D and F. The Dining hall has just one. |
| 1:00 | Count appears: 7 circles, 7 lines | Let's count. Seven buildings, so seven vertices. Seven walkways, so seven edges. Notice that each walkway counts once, even though it touches two buildings. |
| 1:15 | **⏸ CHECKPOINT 1** | How many vertices and how many edges does the campus graph have? |
| 1:20 | Title: data structure | Right: seven of each. A graph is a **data structure**. That means it's a way of organising data so a program can use it, just like the queue you met in COS110. |
| 1:40 | Title: algorithm | An **algorithm** is a list of steps that solves a problem. A data structure holds the information; an algorithm works with it. |
| 1:55 | A tour path lights up building by building | One common job is to visit every vertex by following edges, like a tour guide walking to every building on campus. This is called a **graph traversal**. In Module 3 you'll learn BFS, an algorithm for doing it. |
| 2:20 | **⏸ CHECKPOINT 2** | A tour guide walks along walkways until she has visited every building once. In graph terms, what is she doing? |
| 2:25 | Summary card: graph = vertices + edges | So: a graph is a data structure made of vertices and edges. A traversal is an algorithm that visits them. Next, you'll practise reading graphs and build the campus graph yourself. |

---

## Video 2 — One-way or two-way? (≈ 1:45)

Plays after "Build the campus graph".

**On screen:** the shuttle graph. A → D → G → A, drawn with arrows.

**Text description:** Directed graph with 3 vertices: A is the Admin block; D is the Dining hall; G is the Green (sports field). It has 3 edges: A → D, D → G, G → A. Each edge points from the first vertex to the second.

| Time | On screen | Narration |
|---|---|---|
| 0:00 | Campus graph, plain lines | Every walkway on campus can be walked both ways. When the edges of a graph work in both directions, we draw them as plain lines and call the graph **undirected**. |
| 0:20 | Shuttle bus icon; shuttle graph with arrows | The campus shuttle is different. It drives one loop, in one direction only: from the Admin block to the Dining hall, then to the Green, then back to the Admin block. |
| 0:40 | Arrow A → D pulses | To show that, each edge gets an arrow. An edge with an arrow can only be followed the way it points. A graph with arrows is called **directed**. |
| 0:55 | D highlighted, arrow D → G | So from the Dining hall, the shuttle can only take you to the Green. |
| 1:10 | **⏸ CHECKPOINT 3** | Can you ride the shuttle directly from the Dining hall to the Admin block? |
| 1:15 | Path D → G → A highlighted | No. The edge between them points from A to D. To get back to the Admin block, you ride D → G → A. |
| 1:25 | Two people with arrows both ways between them | One last trap. If two people follow each other online, there are two arrows: one each way. The graph is still directed, because each follow is its own one-way edge. |
| 1:40 | Summary card | Plain lines: undirected. Arrows: directed. Next, you'll classify some graphs yourself. |

### Notes for whoever records

- Draw the graph exactly as above, with the letters and names showing, so it matches the activities.
- Pause the recording at each checkpoint time; the player pauses there automatically (FR-3.3).
- If a time drifts while recording, set the checkpoint's time in the video editor instead.
- If the video isn't ready in time, the transcript (this text) works as the text version of the segment.

---

## Checkpoint questions (enter these in the video editor)

Videos and their checkpoints are made in the app, not in the fixtures: upload each video in the
staff portal, attach it to its segment in module 1, then add these questions at these times.
In each, **(✓)** marks the right answer, the text after the arrow (→) on a wrong option is its feedback, and the four hints go in the editor's hint ladder.

### Video 1, checkpoint 1 (1:15)

How many **vertices** and how many **edges** does the campus graph have?

- 7 vertices and 7 edges **(✓)**
- 7 vertices and 14 edges → Not quite. You counted each walkway twice. A walkway between two buildings is one edge, even though it touches two vertices. Count the lines on the map, not their ends.
- 14 vertices and 7 edges → Not quite. You swapped vertices and edges. Vertices are the buildings (the circles). Edges are the walkways (the lines). Count the circles first, then the lines.
- 6 vertices and 7 edges → Not quite. One building is missing. Every building is a vertex, including the Dining hall (D), which has only one walkway. Count the circles again from A to G.

Hints:

1. A vertex is a building. An edge is a walkway.
2. Count the circles for vertices, and the lines for edges.
3. The buildings are labelled A to G. Each line between two circles is one edge.
4. Answer: 7 vertices (A to G) and 7 edges (A–C, A–E, B–C, B–G, C–F, D–E, E–F).

### Video 1, checkpoint 2 (2:20)

A campus tour guide walks along walkways until she has visited every building once. In graph terms, what is she doing?

- A graph traversal **(✓)**
- Building a data structure → Not quite. The graph (the map) is the data structure. It already exists. The guide is using it, not building it. Ask yourself: is she storing data, or moving through it?
- Adding edges to the graph → Not quite. She only walks along walkways that already exist. She doesn't add any new ones. Think about the word for visiting every vertex in turn.

Hints:

1. She visits every building, moving along walkways.
2. The video gave a name to visiting every vertex of a graph.
3. The word starts with "t" and means "travelling through".
4. Answer: a graph traversal, which means visiting every vertex by following edges.

### Video 2, checkpoint 3 (1:10)

The campus shuttle only drives one way around its loop. Look at the shuttle graph. Can you ride the shuttle **directly** from the Dining hall (D) to the Admin block (A)?

- No. The edge between them points from A to D. **(✓)**
- Yes. A and D are joined by an edge, so you can go either way → Not in a directed graph. This graph has arrows. The edge between A and D only points from A to D. Check which way the arrow on that edge points.
- Yes. The shuttle visits both stops → Not directly. Visiting both stops doesn't mean there's an edge from D to A. The only edge out of D goes to G. Follow the arrows leaving D.

Hints:

1. This graph has arrows on its edges.
2. You can only travel along an edge in the direction of its arrow.
3. Find the edge between A and D. Which end is the arrow pointing to?
4. Answer: no. The edge is A → D, so from D you must go D → G → A.
