"""The quick check questions (FR-8.2, #214): every answer is worked out here by code.

Each module 1 to 5 has four multiple choice questions. Every right answer is checked against the
BFS engine (app/services/bfs.py), the Graph class module 2 builds, the BFS module 4 builds (run
as Python), a faulty BFS run as Python, or the content the module teaches (module 1's key terms,
module 3's "when is BFS the right tool?"). Where it can be, every wrong option is checked to be
wrong the same way.
"""

import json
import re
from collections import deque

import pytest
from test_module_2 import run as run_graph_class
from test_module_4 import reference, setup_from
from test_module_4 import run as run_module_bfs

from app.schemas.graphs import GraphEdge, GraphScenarioOut
from app.seed import ActivityFixture, FixtureFile, read_fixtures
from app.services.bfs import run_bfs
from app.services.quick_check import PASS_MARK, QUICK_CHECK_SIZE

CONTENT: FixtureFile = read_fixtures()
ITEMS = [a for a in CONTENT.activities if a.purpose == "test_out"]
DASH = "\N{EN DASH}"
EDGE = re.compile(rf"\b([A-Z]) ?({DASH}|→) ?([A-Z])\b")


def item(activity_id: int) -> ActivityFixture:
    return next(a for a in ITEMS if a.id == activity_id)


def labels(activity_id: int) -> dict[str, str]:
    return {o["id"]: o["label"] for o in item(activity_id).config["options"]}


def right(activity_id: int) -> str:
    return labels(activity_id)[item(activity_id).solution["correct"]]


def wrong(activity_id: int) -> list[str]:
    a = item(activity_id)
    return [label for key, label in labels(activity_id).items() if key != a.solution["correct"]]


def edges(text: str) -> list[tuple[str, str, bool]]:
    return [(u, v, arrow == "→") for u, arrow, v in EDGE.findall(text)]


def scenario(text: str, start: str, vertices: str = "") -> GraphScenarioOut:
    found = edges(text)
    names = sorted({v for u, w, _ in found for v in (u, w)} | set(vertices))
    return GraphScenarioOut(
        id=0,
        name="",
        directed=any(d for _, _, d in found),
        vertices=names,
        edges=[GraphEdge(source=u, target=v) for u, v, _ in found],
        start_vertex=start,
    )


def adjacency(text: str, vertices: str = "") -> dict[str, list[str]]:
    found = edges(text)
    graph: dict[str, list[str]] = {v: [] for v in vertices}
    for u, v, directed in found:
        graph.setdefault(u, []).append(v)
        graph.setdefault(v, [])
        if not directed:
            graph[v].append(u)
    return graph


def bfs(
    graph: dict[str, list[str]],
    start: str,
    *,
    late: bool = False,
    extra: bool = False,
    stack: bool = False,
) -> list[str]:
    """The module's BFS, or one of the faulty versions the questions describe: `late` marks a
    vertex visited only when it leaves the queue, `extra` adds every vertex it didn't reach to the
    end, `stack` takes from the back of the queue. Stops after 50 steps (a faulty one may loop)."""
    visited = set() if late else {start}
    queue = deque([start])
    order: list[str] = []
    while queue and len(order) < 50:
        v = queue.pop() if stack else queue.popleft()
        if late:
            visited.add(v)
        order.append(v)
        for n in sorted(graph[v]):
            if n not in visited:
                if not late:
                    visited.add(n)
                queue.append(n)
    if extra:
        order += [v for v in graph if v not in order]
    return order


def islands(label: str) -> dict[str, list[str]]:
    return adjacency(label, "A")


def test_each_module_1_to_5_has_a_full_quick_check() -> None:
    by_module: dict[int, list[ActivityFixture]] = {}
    for a in ITEMS:
        assert a.module_id is not None
        by_module.setdefault(a.module_id, []).append(a)
    assert sorted(by_module) == [1, 2, 3, 4, 5]
    assert all(len(found) == QUICK_CHECK_SIZE for found in by_module.values())
    assert PASS_MARK == QUICK_CHECK_SIZE - 1


@pytest.mark.parametrize("a", ITEMS, ids=lambda a: str(a.id))
def test_four_options_a_reason_for_every_wrong_one_and_no_hints(a: ActivityFixture) -> None:
    options = [o["id"] for o in a.config["options"]]
    assert len(options) == 4  # blind guessing passes 3 of 4 about 5% of the time
    assert set(a.solution["feedback"]) == set(options) - {a.solution["correct"]}
    assert a.solution["explanation"]
    assert a.hints == []
    assert "worked example" not in json.dumps(a.solution).lower()


def test_the_quick_check_items_appear_in_no_segment() -> None:
    ids = {a.id for a in ITEMS}
    for module in CONTENT.modules:
        for segment in module.segments:
            assert segment.activity_id not in ids
            assert segment.skip_check_activity_id not in ids


# Module 1


def test_103_counts_the_edges_and_finds_the_busiest_vertex() -> None:
    graph = adjacency(item(103).config["prompt"])
    busiest = max(graph, key=lambda v: len(graph[v]))
    assert (
        right(103)
        == f"{len(edges(item(103).config['prompt']))} edges; {busiest} has the most neighbours"
    )


def test_150_the_traversal_is_module_1s_example_of_one() -> None:
    terms = next(a for a in CONTENT.activities if a.id == 102)
    term_of_example = {}
    for left in terms.config["left"]:
        definition = next(
            r["label"]
            for r in terms.config["right"]
            if r["id"] == terms.solution["pairs"][left["id"]]
        )
        example = definition.split("Example: ")[1]
        term_of_example[example.lower()] = left["label"]
    assert term_of_example[right(150).lower()] == "Graph traversal"
    assert sorted(term_of_example[w.lower()] for w in wrong(150)) == [
        "Algorithm",
        "Data structure",
        "Graph",
    ]


def test_151_arrows_make_it_directed_and_each_is_one_edge() -> None:
    found = edges(item(151).config["prompt"])
    kind = "Directed" if all(d for _, _, d in found) else "Undirected"
    assert right(151) == f"{kind}, with {len(found)} edges"


def test_152_the_stops_are_vertices_and_the_two_way_buses_undirected_edges() -> None:
    prompt = item(152).config["prompt"]
    stops = re.findall(r"\(([A-Z])\)", prompt)
    routes = {frozenset(p) for p in re.findall(r"\b([A-Z]) and ([A-Z])\b", prompt)}
    assert len(stops) == 4
    found = edges(right(152))
    assert right(152).startswith(f"{len(stops)} vertices, the stops")
    assert not any(d for _, _, d in found)
    assert {frozenset((u, v)) for u, v, _ in found} == routes
    for label in wrong(152):
        other = edges(label)
        assert (
            not other
            or any(d for _, _, d in other)
            or {frozenset((u, v)) for u, v, _ in other} != routes
        )


# Module 2


def calls(prompt: str) -> str:
    """The Graph calls a prompt names, as code."""
    directed = "directed=True" in prompt
    found = re.findall(r"g\.(add_vertex|add_edge)\(([^)]*)\)", prompt)
    return "\n".join([f"g = Graph(directed={directed})"] + [f"g.{f}({args})" for f, args in found])


@pytest.mark.parametrize("activity_id", [203, 250])
def test_the_dictionary_is_what_the_graph_class_builds(activity_id: int) -> None:
    built = run_graph_class(calls(item(activity_id).config["prompt"]))
    assert json.loads(right(activity_id)) == built
    assert all(json.loads(label) != built for label in wrong(activity_id))


def test_251_the_edges_build_the_dictionary() -> None:
    stored = json.loads(re.search(r"(\{.*\})", item(251).config["prompt"]).group(1))  # type: ignore[union-attr]

    def build(label: str) -> dict[str, list[str]]:
        code = "g = Graph()\n" + "\n".join(f'g.add_edge("{u}", "{v}")' for u, v, _ in edges(label))
        return run_graph_class(code)

    assert build(right(251)) == stored
    assert all(build(label) != stored for label in wrong(251))


def test_252_add_vertex_adds_an_empty_list() -> None:
    code = 'g = Graph()\ng.add_edge("P", "Q")\ng.add_vertex("R")'
    built = run_graph_class(code)
    assert json.loads(right(252)) == built
    assert all(json.loads(label) != built for label in wrong(252))


# Module 3


def test_314_the_queue_after_c_is_the_engines() -> None:
    campus = GraphScenarioOut(**next(g for g in CONTENT.graphs if g.id == 4).model_dump())
    after_c = next(s for s in run_bfs(campus).steps if s.visited_vertex == "C")
    assert right(314) == ", ".join(after_c.queue)
    assert all(label != right(314) for label in wrong(314))


def test_350_the_one_that_isnt_a_job_for_bfs_is_module_3s_not_a_fit() -> None:
    fits = next(a for a in CONTENT.activities if a.id == 313)
    reasons = {r["id"]: r["label"] for r in fits.config["right"]}
    verdict = {
        s["label"]: reasons[fits.solution["pairs"][s["id"]]].startswith("Good fit")
        for s in fits.config["left"]
    }
    assert set(labels(350).values()) == set(verdict)
    assert [label for label, fit in verdict.items() if not fit] == [right(350)]


def test_351_the_order_is_the_engines() -> None:
    order = run_bfs(scenario(item(351).config["prompt"], "A")).order
    assert right(351) == ", ".join(order)
    assert all(label != right(351) for label in wrong(351))


def test_352_the_fewest_edges_is_the_engines() -> None:
    result = run_bfs(scenario(item(352).config["prompt"], "P"))
    found_by = {v: s.visited_vertex for s in result.steps for v in s.discovered}
    path = ["U"]
    while path[-1] != "P":
        path.append(found_by[path[-1]])
    assert right(352) == str(len(path) - 1)


# Module 4


@pytest.mark.parametrize(("activity_id", "start"), [(403, "W"), (450, "A"), (451, "P")])
def test_what_the_module_s_bfs_returns(activity_id: int, start: str) -> None:
    prompt = item(activity_id).config["prompt"]
    returned = run_module_bfs(reference(), setup_from(prompt), start)
    assert json.loads(right(activity_id)) == returned
    assert returned == run_bfs(scenario(prompt, start)).order
    assert all(json.loads(label) != returned for label in wrong(activity_id))


def test_452_pop_takes_from_the_back() -> None:
    prompt = item(452).config["prompt"]
    code = reference()
    assert "queue.popleft()" in code
    returned = run_module_bfs(
        code.replace("queue.popleft()", "queue.pop()"), setup_from(prompt), "A"
    )
    assert returned == bfs(adjacency(prompt), "A", stack=True)
    assert json.loads(right(452)) == returned
    assert returned != run_bfs(scenario(prompt, "A")).order
    assert all(json.loads(label) != returned for label in wrong(452))


# Module 5


def test_503_the_late_visited_bug_visits_a_vertex_twice_on_a_cycle() -> None:
    cycle = adjacency(f"A{DASH}B, A{DASH}C, B{DASH}D, C{DASH}D")
    faulty = bfs(cycle, "A", late=True)
    assert len(faulty) > len(set(faulty))
    assert set(faulty) == set(cycle)
    assert "visited twice" in right(503)


@pytest.mark.parametrize(("activity_id", "fault"), [(550, "late"), (551, "extra")])
def test_only_the_right_test_graph_shows_the_bug(activity_id: int, fault: str) -> None:
    def shows(label: str) -> bool:
        graph = islands(label)
        return bfs(graph, "A", **{fault: True}) != bfs(graph, "A")

    assert shows(right(activity_id))
    assert not any(shows(label) for label in wrong(activity_id))


def test_552_the_expected_order_is_the_engines() -> None:
    prompt = item(552).config["prompt"]
    order = run_bfs(scenario(prompt, "A")).order
    assert json.loads(right(552)) == order == bfs(adjacency(prompt), "A")
    assert all(json.loads(label) != order for label in wrong(552))


def test_the_test_bfs_here_is_the_engines() -> None:
    for text in (
        f"A{DASH}B, B{DASH}C, A{DASH}C",
        f"A{DASH}B, C{DASH}D",
        f"A{DASH}C, A{DASH}B, B{DASH}D",
    ):
        assert bfs(adjacency(text), "A") == run_bfs(scenario(text, "A")).order
