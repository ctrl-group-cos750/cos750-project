"""Graph scenarios and the BFS steps computed from them (SE document FR-6, §10).

The BFS steps are computed server side by the one tested engine (app/services/bfs.py), so the
animation, the next-vertex prediction and the trace table can never disagree with what the lessons
teach (SE document, decision "BFS computed server-side"). Neighbours are always taken in
alphabetical order of their labels (FR-6.5).
"""

from app.schemas.base import ApiModel

VERTEX = r"^[A-Za-z0-9 _-]{1,32}$"


class GraphEdge(ApiModel):
    """A single edge. For an undirected graph the pair is unordered; for a directed graph the edge
    goes from `source` to `target`."""

    source: str
    target: str


class GraphScenarioOut(ApiModel):
    """A graph scenario as the frontend renders it (FR-6.1): the vertices, the edges, whether it is
    directed and where the traversal starts."""

    id: int
    name: str
    directed: bool
    vertices: list[str]
    edges: list[GraphEdge]
    start_vertex: str


class BfsStep(ApiModel):
    """One step of the traversal: the vertex just visited (dequeued), and the state after it
    (SE document FR-6.2). `discovered` are the vertices this step added to the queue, in the
    alphabetical order they were enqueued; `frontier_edges` are the edges along which they were
    discovered (from the visited vertex to each newly discovered neighbour)."""

    visited_vertex: str
    queue: list[str]
    visited: list[str]
    order: list[str]
    discovered: list[str]
    frontier_edges: list[GraphEdge]


class BfsResult(ApiModel):
    """The whole traversal from the start vertex: the final visit order and every step, ready for
    the visualiser to animate without further server calls (FR-6.1, NFR-P4)."""

    start_vertex: str
    order: list[str]
    steps: list[BfsStep]
