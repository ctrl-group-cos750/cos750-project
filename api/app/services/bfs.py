"""The BFS engine (SE document FR-6, §10, NFR-M1).

Pure and deterministic: it takes a graph scenario and returns the breadth-first traversal from the
start vertex as an ordered list of steps. It runs no I/O and touches no database, so it is unit
tested in isolation and the endpoint, the animation, the next-vertex prediction and the trace table
all share this one source of truth (SE document decision "BFS computed server-side").

Rules the lessons teach, encoded here:
  * Neighbours are taken in alphabetical order of their labels (FR-6.5), so a correct prediction is
    always marked correct.
  * Standard single-source BFS: a vertex is enqueued once, when it is first discovered, and is
    visited (dequeued) once. Vertices not reachable from the start are never visited.
"""

from app.schemas.graphs import BfsResult, BfsStep, GraphEdge, GraphScenarioOut

UNKNOWN_START = "The start vertex is not one of the graph's vertices."
DUPLICATE_VERTEX = "The graph lists the same vertex more than once."
UNKNOWN_EDGE_ENDPOINT = "An edge refers to a vertex that is not in the graph."


class InvalidGraph(ValueError):
    """A scenario the engine refuses to run: a missing start vertex, a repeated vertex, or an edge
    to a vertex the graph does not declare (SE document FR-6 acceptance: invalid scenarios are
    rejected with a clear error)."""


def _adjacency(scenario: GraphScenarioOut) -> dict[str, list[str]]:
    """Neighbours of each vertex, each list sorted alphabetically (FR-6.5). An undirected edge adds
    both directions; a directed edge adds only source -> target. Parallel edges and self-loops
    collapse to one neighbour, since BFS discovers a vertex once either way."""
    neighbours: dict[str, set[str]] = {v: set() for v in scenario.vertices}
    for edge in scenario.edges:
        neighbours[edge.source].add(edge.target)
        if not scenario.directed:
            neighbours[edge.target].add(edge.source)
    return {vertex: sorted(targets) for vertex, targets in neighbours.items()}


def neighbours(scenario: GraphScenarioOut) -> dict[str, list[str]]:
    """Each vertex's neighbours in the order BFS takes them (alphabetical), for code that steps
    BFS from a state of its own, such as follow-through marking of a trace table."""
    return _adjacency(scenario)


def _validate(scenario: GraphScenarioOut) -> None:
    if len(set(scenario.vertices)) != len(scenario.vertices):
        raise InvalidGraph(DUPLICATE_VERTEX)
    known = set(scenario.vertices)
    if scenario.start_vertex not in known:
        raise InvalidGraph(UNKNOWN_START)
    for edge in scenario.edges:
        if edge.source not in known or edge.target not in known:
            raise InvalidGraph(UNKNOWN_EDGE_ENDPOINT)


def run_bfs(scenario: GraphScenarioOut) -> BfsResult:
    """Breadth-first traversal from `scenario.start_vertex`.

    Each step dequeues one vertex (the step's `visited_vertex`) and enqueues its not-yet-discovered
    neighbours in alphabetical order; the step records the queue, visited set and order after it,
    and the neighbours it discovered together with the edges it discovered them along. Raises
    `InvalidGraph` for a scenario the engine cannot run.
    """
    _validate(scenario)
    adjacency = _adjacency(scenario)

    start = scenario.start_vertex
    queue: list[str] = [start]
    discovered: set[str] = {start}  # enqueued at least once; stops a vertex being queued twice
    order: list[str] = []
    steps: list[BfsStep] = []

    while queue:
        current = queue.pop(0)
        order.append(current)
        newly_discovered: list[str] = []
        frontier_edges: list[GraphEdge] = []
        for neighbour in adjacency[current]:
            if neighbour not in discovered:
                discovered.add(neighbour)
                queue.append(neighbour)
                newly_discovered.append(neighbour)
                frontier_edges.append(GraphEdge(source=current, target=neighbour))
        steps.append(
            BfsStep(
                visited_vertex=current,
                queue=list(queue),
                visited=list(order),
                order=list(order),
                discovered=newly_discovered,
                frontier_edges=frontier_edges,
            )
        )

    return BfsResult(start_vertex=start, order=order, steps=steps)
