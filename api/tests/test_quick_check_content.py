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
from test_module_4 import reference, setup_from, step_budget
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


# What each option of 150 is, by the two questions module 1's worked example asks: does it keep
# something or do something, and does it involve things joined by connections? Every option uses
# "every", so the word that defines a traversal is no cue (round 2 review of #215, content 7).
TERM_150 = {
    "A recipe book's index: every dish, with its page number.": ("keeps", False),
    "Adding up every number in a list, one after another.": ("does", False),
    "Opening a web page, then every page it links to, and so on.": ("does", True),
    "Every town in a province, and the roads that join them.": ("keeps", True),
}
TERMS = {
    ("keeps", False): "Data structure",
    ("does", False): "Algorithm",
    ("keeps", True): "Graph",
    ("does", True): "Graph traversal",
}


def test_150_the_traversal_is_new_and_no_keyword_finds_it() -> None:
    assert set(labels(150).values()) == set(TERM_150)
    assert TERMS[TERM_150[right(150)]] == "Graph traversal"
    assert sorted(TERMS[TERM_150[w]] for w in wrong(150)) == [
        "Algorithm",
        "Data structure",
        "Graph",
    ]
    assert all("every" in label.lower() for label in labels(150).values())
    # None of module 1's key-term examples comes back, so recall of 102 is no answer either.
    terms = next(a for a in CONTENT.activities if a.id == 102)
    examples = " ".join(r["label"].split("Example: ")[-1].lower() for r in terms.config["right"])
    assert not any(label.lower().rstrip(".") in examples for label in labels(150).values())


def test_151_direction_comes_from_what_a_follow_means_not_an_arrow() -> None:
    prompt = item(151).config["prompt"]
    assert "→" not in prompt
    assert "arrow" not in prompt.lower()
    follows = {("Lindi", "Musa"), ("Musa", "Lindi"), ("Lindi", "Nandi")}
    assert all(name in prompt for pair in follows for name in pair)
    one_way = any((v, u) not in follows for u, v in follows)
    assert one_way
    assert right(151) == f"{'Directed' if one_way else 'Undirected'}, with {len(follows)} edges"


def test_152_sitting_side_by_side_is_undirected_and_the_prompt_never_says_so() -> None:
    prompt = item(152).config["prompt"]
    assert "both ways" not in prompt
    assert "two-way" not in prompt
    people = re.findall(r"\(([A-Z])\)", prompt)
    pairs = {frozenset(p) for p in re.findall(r"\b([A-Z]) and ([A-Z])\b", prompt)}
    assert len(people) == 4
    assert pairs == {frozenset(people[i : i + 2]) for i in range(3)}  # neighbours in the row
    found = edges(right(152))
    assert right(152).startswith(f"{len(people)} vertices, the learners")
    assert not any(d for _, _, d in found)
    assert {frozenset((u, v)) for u, v, _ in found} == pairs
    for label in wrong(152):
        other = edges(label)
        assert (
            not other
            or any(d for _, _, d in other)
            or {frozenset((u, v)) for u, v, _ in other} != pairs
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
    """314 named "the campus graph" with no walkways, so a student who skipped module 1 couldn't
    answer it (round 2 review of #215, content 2). Its prompt lists them, and they are graph 4's."""
    campus = GraphScenarioOut(**next(g for g in CONTENT.graphs if g.id == 4).model_dump())
    listed = scenario(item(314).config["prompt"], "A")
    assert {frozenset((e.source, e.target)) for e in listed.edges} == {
        frozenset((e.source, e.target)) for e in campus.edges
    }
    after_c = next(s for s in run_bfs(listed).steps if s.visited_vertex == "C")
    assert right(314) == ", ".join(after_c.queue)
    assert all(label != right(314) for label in wrong(314))


def test_350_the_one_that_isnt_a_job_for_bfs_is_module_3s_not_a_fit() -> None:
    fits = next(a for a in CONTENT.activities if a.id == 313)
    reasons = {r["id"]: r["label"] for r in fits.config["right"]}
    verdict = {
        s["label"]: reasons[fits.solution["pairs"][s["id"]]].startswith("Good fit")
        for s in fits.config["left"]
    }
    # Every option is one of 313's situations, and the only one that isn't a job for BFS is the
    # answer (313 has more situations than the four options here).
    options = set(labels(350).values())
    assert options <= set(verdict)
    assert [label for label, fit in verdict.items() if not fit and label in options] == [right(350)]


def test_351_the_order_is_the_engines() -> None:
    order = run_bfs(scenario(item(351).config["prompt"], "A")).order
    assert right(351) == ", ".join(order)
    assert all(label != right(351) for label in wrong(351))


def test_352_the_fewest_edges_is_the_engines() -> None:
    prompt = item(352).config["prompt"]
    start, goal = re.search(r"from ([A-Z]) to ([A-Z])\?", prompt).groups()  # type: ignore[union-attr]
    result = run_bfs(scenario(prompt, start))
    found_by = {v: s.visited_vertex for s in result.steps for v in s.discovered}
    path = [goal]
    while path[-1] != start:
        path.append(found_by[path[-1]])
    assert right(352) == str(len(path) - 1)
    assert all(int(label) != len(path) - 1 for label in wrong(352))


def test_352_is_not_mastery_626s_graph() -> None:
    """352 was 626's bus network minus two edges, with the same letters, and its explanation gave
    the distance 626 adds one to (round 2 review of #215, content 3)."""
    mine = edges(item(352).config["prompt"])
    theirs = edges(next(a for a in CONTENT.activities if a.id == 626).config["prompt"])
    letters = {v for u, w, _ in mine for v in (u, w)}
    assert not letters & {v for u, w, _ in theirs for v in (u, w)}


# Module 4


@pytest.mark.parametrize(("activity_id", "start"), [(403, "W"), (450, "A")])
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


# What each option of 451 does to the module's loop body, as code.
BODIES_451 = {
    "If n is not in found: append n to the queue, and add it to found when it leaves.": (
        "            if n not in found:\n                queue.append(n)",
        "        found.add(v)\n",
    ),
    "If n is not in found: add n to found, then append n to the queue.": (
        "            if n not in found:\n                found.add(n)\n                queue.append(n)",
        "",
    ),
    "Add n to found, then append n to the queue, with no if.": (
        "            found.add(n)\n            queue.append(n)",
        "",
    ),
    "If n is not in found: add n to found, then append n to order.": (
        "            if n not in found:\n                found.add(n)\n                order.append(n)",
        "",
    ),
}


def test_451_builds_the_loop_and_only_the_right_body_makes_working_bfs() -> None:
    """Module 4's quick check only asked what bfs returns, never how to build it (round 2 review
    of #215, content 7). 451 asks for the neighbour loop's body; each option is run as code."""
    code = reference()
    body = "            if n not in found:\n                found.add(n)\n                queue.append(n)"
    after_pop = "        v = queue.popleft()\n"
    assert body in code
    assert after_pop in code
    assert set(labels(451).values()) == set(BODIES_451)
    diamond = f"A{DASH}B, A{DASH}C, B{DASH}D, C{DASH}D"
    expected = run_bfs(scenario(diamond, "A")).order

    def returns(label: str) -> list[str] | None:
        mine, on_pop = BODIES_451[label]
        variant = code.replace(body, mine).replace(after_pop, after_pop + on_pop)
        try:
            with step_budget():
                return run_module_bfs(variant, setup_from(diamond), "A")
        except TimeoutError:
            return None  # it never finishes

    assert returns(right(451)) == expected
    assert all(returns(label) != expected for label in wrong(451))


# Module 5


def test_503_the_late_visited_bug_needs_two_routes_not_a_cycle() -> None:
    """503 said the bug shows "on a graph with a cycle"; mastery 623 has a directed cycle the
    faulty BFS passes and a fork-join with no cycle that it fails (round 2 review of #215)."""
    prompt = item(503).config["prompt"]
    assert "cycle" not in prompt
    assert "two different routes" in prompt
    fork_join = adjacency("A → B, A → C, B → D, C → D")  # two routes to D, no cycle
    faulty = bfs(fork_join, "A", late=True)
    assert len(faulty) > len(set(faulty))
    assert set(faulty) == set(fork_join)
    back_to_start = adjacency("A → B, B → C, C → A")  # a cycle, one route to each vertex
    assert bfs(back_to_start, "A", late=True) == bfs(back_to_start, "A")
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
