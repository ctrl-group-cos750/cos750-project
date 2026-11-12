"""The review paths (ID document §7.6, #148): each opens with a new worked example, then practice
of the same kind as the objective's mastery items, then fresh items. Every graph a worked example
traces is described in words, and every answer it shows is the BFS engine's."""

import re
from typing import Any

import pytest

from app.schemas.graphs import GraphEdge, GraphScenarioOut
from app.seed import ActivityFixture, FixtureFile, SegmentFixture, read_fixtures
from app.services.bfs import run_bfs
from app.services.mastery import MASTERY_MODULE

CONTENT: FixtureFile = read_fixtures()
ACTIVITIES = {a.id: a for a in CONTENT.activities}
PATHS = {r.objective_id: r for r in CONTENT.review_paths}
DASH = "\N{EN DASH}"
ARROW = "\N{RIGHTWARDS ARROW}"


def worked_example(objective: int) -> SegmentFixture:
    return PATHS[objective].segments[0]


def on_path(objective: int, purpose: str) -> list[ActivityFixture]:
    return [
        ACTIVITIES[s.activity_id]
        for s in PATHS[objective].segments
        if s.activity_id is not None and ACTIVITIES[s.activity_id].purpose == purpose
    ]


def graph(directed: bool, edges: list[tuple[str, str]], start: str) -> GraphScenarioOut:
    vertices = sorted({v for e in edges for v in e} | {start})
    return GraphScenarioOut(
        id=0,
        name="",
        directed=directed,
        vertices=vertices,
        edges=[GraphEdge(source=u, target=v) for u, v in edges],
        start_vertex=start,
    )


def described(body: str, directed: bool, edges: list[tuple[str, str]]) -> bool:
    """The body names every edge in words, as the trace screen does (an en dash between the ends, or an arrow)."""
    join = f" {ARROW} " if directed else DASH
    return all(f"{u}{join}{v}" in body for u, v in edges)


def table_rows(body: str) -> list[list[str]]:
    """The cells of each table row that starts with a step number or a vertex."""
    rows = []
    for line in body.splitlines():
        if line.startswith("|") and not line.startswith("|---"):
            rows.append([c.strip().strip("`") for c in line.strip("|").split("|")])
    return rows[1:]  # without the header


def listed(cell: str) -> list[str]:
    return [] if cell in ("(empty)", "none", DASH) else [x.strip() for x in cell.split(",")]


@pytest.mark.parametrize("objective", sorted(PATHS))
def test_each_path_opens_with_a_new_worked_example(objective: int) -> None:
    first = worked_example(objective)
    assert first.kind == "worked_example"
    assert first.body.startswith("**Worked example.**")
    # A new example, worked through in steps, not a summary that sends the student back.
    assert "Go back to" not in first.body
    assert len(re.findall(r"\*\*(?:Step )?\d\.", first.body)) >= 3


# Every kind module 6 and the fresh items use is practised first (constructive alignment).
@pytest.mark.parametrize("objective", sorted(PATHS))
def test_the_practice_includes_every_kind_the_fresh_items_use(objective: int) -> None:
    practice = {a.kind for a in on_path(objective, "review")}
    module_6 = {
        a.kind
        for a in CONTENT.activities
        if a.module_id == MASTERY_MODULE and a.purpose == "mastery" and a.objective_id == objective
    }
    fresh = {a.kind for a in on_path(objective, "mastery")}
    assert module_6 <= practice, (objective, module_6, practice)
    assert fresh <= practice, (objective, fresh, practice)


def test_objective_5s_worked_example_is_the_engines_trace() -> None:
    edges = [("K", "L"), ("K", "N"), ("L", "O"), ("M", "N"), ("M", "O")]
    body = worked_example(5).body
    assert described(body, False, edges)
    steps = run_bfs(graph(False, edges, "K")).steps
    rows = [r for r in table_rows(body) if r[0].isdigit()]
    assert len(rows) == len(steps)
    for row, step in zip(rows, steps, strict=True):
        _, current, queue, visited, order = row
        assert current == step.visited_vertex
        assert listed(queue) == step.queue
        assert sorted(listed(visited)) == sorted(step.visited)
        assert listed(order) == step.order
    assert f"The order is **{', '.join(steps[-1].order)}**." in body
    # Not a graph any trace item uses.
    for a in (a for a in CONTENT.activities if a.kind == "trace"):
        assert set(a.config["vertices"]) != {"K", "L", "M", "N", "O"}


def test_objective_6s_worked_example_runs_as_bfs_does() -> None:
    edges = [("D", "B"), ("D", "A"), ("A", "C"), ("C", "D")]
    body = worked_example(6).body
    assert described(body, True, edges)
    result = run_bfs(graph(True, edges, "D"))
    rows = table_rows(body)
    assert [r[0] for r in rows] == result.order
    for row, step in zip(rows, result.steps, strict=True):
        assert listed(row[2]) == step.queue
        assert listed(row[3]) == step.order
    assert f"The result is **{', '.join(result.order)}**." in body
    # The code in the example is BFS: it gives the engine's order on this graph.
    code = re.search(r"```python\n(.*?)```", body, re.S)
    assert code is not None
    assert run_code(code.group(1), True, edges, "D") == result.order


GRAPH_CLASS = """
class Graph:
    def __init__(self, directed=False):
        self.directed = directed
        self.adjacency = {}

    def add_vertex(self, v):
        if v not in self.adjacency:
            self.adjacency[v] = []

    def add_edge(self, a, b):
        self.add_vertex(a)
        self.add_vertex(b)
        self.adjacency[a].append(b)
        if not self.directed:
            self.adjacency[b].append(a)
"""


def run_code(code: str, directed: bool, edges: list[tuple[str, str]], start: str) -> Any:
    namespace: dict[str, Any] = {}
    exec(  # noqa: S102 - our own fixture code, in our own tests
        "from collections import deque\n" + GRAPH_CLASS + "\n" + code, namespace
    )
    g = namespace["Graph"](directed=directed)
    g.add_vertex(start)
    for u, v in edges:
        g.add_edge(u, v)
    return namespace["bfs"](g, start)


def test_objective_7s_worked_example_tests_say_what_the_code_does() -> None:
    body = worked_example(7).body
    code = re.search(r"```python\n(.*?)```", body, re.S)
    assert code is not None
    faulty = code.group(1)
    fixed = faulty.replace("graph.adjacency[start]", "graph.adjacency[v]")
    assert fixed != faulty
    tests = {
        "1": ([("A", "B"), ("A", "C"), ("A", "D")], True),
        "2": ([("A", "B"), ("B", "C")], False),
        "3": ([("A", "B"), ("C", "D")], True),
    }
    rows = {r[0].split(",")[0]: r for r in table_rows(body)}
    for name, (edges, passes) in tests.items():
        assert described(rows[name][1], False, edges)
        want = run_bfs(graph(False, edges, "A")).order
        assert listed(rows[name][3]) == want
        assert (run_code(faulty, False, edges, "A") == want) is passes, name
        assert run_code(fixed, False, edges, "A") == want, name
    assert "test 2 **fails**" in body
    assert "test 1 **passes**" in body
    assert "test 3 **passes**" in body
