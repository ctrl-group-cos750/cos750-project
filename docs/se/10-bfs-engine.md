# BFS Engine Design

## Responsibilities
A self-contained `BfsEngine` module in the backend, independent of web/HTTP concerns, that:
1. Accepts a graph scenario (nodes, edges, directedness) and a start node.
2. Produces the BFS traversal **order** and a list of **steps** rich enough for the frontend to animate without re-deriving algorithm logic.

## Graph representation
- Input (from `GraphScenario`): `nodes` as a list of ids/labels; `edges` as `{source, target, weight?}`; `directed` flag.
- Internal: an **adjacency list** `dict[node, list[node]]`. For undirected graphs, each edge is inserted in both directions. Neighbour ordering is made **deterministic** (e.g. sorted by node id/insertion order) so animations are reproducible and testable.

## Algorithm & step emission
Standard BFS using a FIFO queue (`collections.deque`) and a `visited` set. On each loop iteration the engine emits a **step record** capturing observable state:

```
dequeue current node
emit step: { index, action: "visit", node: current,
             queueBefore, visited(after marking),
             discovered: [newly enqueued neighbours this step],
             queueAfter, frontierEdges: [(current, neighbour) ...] }
for each neighbour of current (deterministic order):
    if neighbour not visited and not already queued:
        mark discovered, enqueue
```

The returned payload (see §9.4) contains:
- `order`: the final visitation order (teaching the core result),
- `steps`: per-step snapshots (queue before/after, visited set, newly discovered nodes, edges explored) so the frontend can highlight nodes/edges and show queue state at each step.

## Design properties
- **Deterministic** output for a given scenario + start node (reproducible animations, easy snapshot tests).
- **Pure/stateless** computation (no DB access inside the engine; scenario data passed in).
- **Validated inputs** (start node exists, edges reference known nodes) — malformed scenarios rejected with a clear error.
- **Precomputed, not streamed:** the entire step list is returned in one response; the frontend controls playback locally (supports step-back and scrubbing without extra calls). This is settled for Draft 1 given the confirmed small-graph scope (≤ ~50 nodes); it may be revisited only if graphs grow substantially in a later draft.

## Testing
- Unit tests over known graphs with asserted `order` and `steps` (directed and undirected; disconnected graph handling; single-node; start-node validation).
