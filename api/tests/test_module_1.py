"""Module 1 (What is a graph?, #83): every graph fact the content states is true of its graph.

The campus is graph 4 (graphs.json), the same graph module 3 runs BFS on, so the module's answers
are checked against it with the engine. The other graphs live only in the activities' text (their
text description, WCAG 1.1.1), so those answers are checked against the edges the text lists.
Plus the content rules from issue #83: four hint levels on every activity, and feedback for
every wrong answer.
"""

import re

import pytest

from app.schemas.graphs import GraphScenarioOut
from app.seed import ActivityFixture, FixtureFile, read_fixtures
from app.services.bfs import run_bfs

CONTENT: FixtureFile = read_fixtures()
CAMPUS = GraphScenarioOut(**next(g for g in CONTENT.graphs if g.id == 4).model_dump())
MODULE = next(m for m in CONTENT.modules if m.id == 1)
ACTIVITIES = [a for a in CONTENT.activities if a.module_id == 1]
DASH = "\N{EN DASH}"  # the content joins an undirected edge's ends with it
EDGE = re.compile(rf"\b([A-Z]) ?({DASH}|→) ?([A-Z])\b")


def activity(activity_id: int) -> ActivityFixture:
    return next(a for a in ACTIVITIES if a.id == activity_id)


def chosen_label(activity_id: int) -> str:
    a = activity(activity_id)
    correct = a.solution["correct"]
    return str(next(o["label"] for o in a.config["options"] if o["id"] == correct))


def right_label(a: ActivityFixture, left_id: str) -> str:
    right_id = a.solution["pairs"][left_id]
    return str(next(r["label"] for r in a.config["right"] if r["id"] == right_id))


def edges_in(text: str) -> set[frozenset[str] | tuple[str, str]]:
    """The edges a text lists: an edge written with a dash is undirected, `A → C` directed."""
    return {(u, v) if arrow == "→" else frozenset((u, v)) for u, arrow, v in EDGE.findall(text)}


def campus_edges() -> set[frozenset[str] | tuple[str, str]]:
    return {frozenset((e.source, e.target)) for e in CAMPUS.edges}


def test_every_activity_is_shown_once_and_every_objective_has_one() -> None:
    shown = [s.activity_id for s in MODULE.segments if s.activity_id is not None]
    skip_checks = [s.skip_check_activity_id for s in MODULE.segments if s.skip_check_activity_id]
    assert sorted(shown + skip_checks) == sorted(a.id for a in ACTIVITIES)
    assert {a.objective_id for a in ACTIVITIES} == {1, 2, 3}


def test_the_module_opens_with_the_campus_and_its_puzzle() -> None:  # Gagné event 1
    first, second = MODULE.segments[:2]
    assert first.kind == "text"
    assert second.activity_id == 101
    assert edges_in(first.body) == campus_edges()
    assert all(vertex in first.body for vertex in CAMPUS.vertices)


@pytest.mark.parametrize("a", ACTIVITIES, ids=lambda a: str(a.id))
def test_every_activity_has_four_hint_levels_and_the_last_gives_the_answer(
    a: ActivityFixture,
) -> None:
    assert [h.level for h in a.hints] == [1, 2, 3, 4]
    assert a.hints[-1].body.startswith("Answer:")


@pytest.mark.parametrize("a", ACTIVITIES, ids=lambda a: str(a.id))
def test_every_wrong_answer_has_feedback(a: ActivityFixture) -> None:
    if a.kind == "multiple_choice":
        wrong = {o["id"] for o in a.config["options"]} - {a.solution["correct"]}
    else:
        wrong = {item["id"] for item in a.config["left"]}
    assert set(a.solution["feedback"]) == wrong


def test_the_puzzle_answer_is_the_fewest_walkways_from_a_to_g() -> None:
    assert edges_in(activity(101).config["prompt"]) == campus_edges()
    found_by = {v: s.visited_vertex for s in run_bfs(CAMPUS).steps for v in s.discovered}
    path = ["G"]
    while path[-1] != "A":
        path.append(found_by[path[-1]])
    assert path[::-1] == ["A", "C", "B", "G"]
    assert chosen_label(101) == str(len(path) - 1)
    assert "A → C → B → G" in activity(101).hints[-1].body


def test_the_worked_example_reads_the_campus() -> None:
    worked = next(s for s in MODULE.segments if s.kind == "worked_example")
    assert worked.skip_check_activity_id == 103
    # It shows the method on one walkway, which is a campus edge, and leaves the rest to activity
    # 105: a list of every walkway beside its edge would make 105 a copying task (#147).
    shown = edges_in(worked.body)
    assert shown
    assert shown <= campus_edges()
    assert len(shown) < len(campus_edges()) - 3
    n, m = len(CAMPUS.vertices), len(CAMPUS.edges)
    assert f"**Result:** {n} vertices, {m} edges, undirected." in worked.body
    neighbours_of_e = sorted(v for e in campus_edges() if "E" in e for v in set(e) - {"E"})
    assert "E's neighbours are " + ", ".join(neighbours_of_e[:-1]) in worked.body


def test_the_skip_check_answer_counts_the_edges_and_finds_the_busiest_vertex() -> None:
    a = activity(103)
    edges = edges_in(a.config["prompt"])
    degree: dict[str, int] = {}
    for edge in edges:
        for vertex in edge:
            degree[vertex] = degree.get(vertex, 0) + 1
    busiest = max(degree, key=lambda v: degree[v])
    assert chosen_label(103) == f"{len(edges)} edges; {busiest} has the most neighbours"


def test_the_bus_stop_labels_name_the_stops_and_roads_the_prompt_lists() -> None:
    a = activity(104)
    stops = dict(re.findall(r"the (\w+) \(([A-Z])\)", a.config["prompt"]))
    roads = edges_in(a.config["prompt"])
    for item in a.config["left"]:
        answer = right_label(a, item["id"])
        named = re.findall(r"the (\w+)", item["label"].removeprefix("The "))
        if item["label"].endswith("bus stop"):
            assert answer == f"Vertex {stops[item['label'].split()[1]]}"
        else:
            u, v = (stops[name] for name in named[-2:])
            assert frozenset((u, v)) in roads
            assert answer in (f"Edge {u}{DASH}{v}", f"Edge {v}{DASH}{u}")


def test_the_built_graph_is_the_campus() -> None:
    a = activity(105)
    key = a.config["prompt"].split("is a vertex: ")[1].split(".")[0]  # "A Admin block, B …"
    names = {name: letter for letter, name in re.findall(r"\b([A-G]) ([^,]+)", key)}
    built = set()
    for item in a.config["left"]:
        u, v = item["label"].removeprefix("Walkway: ").split(f" {DASH} ")
        answer = right_label(a, item["id"])
        assert answer == f"Edge {names[u]}{DASH}{names[v]}"
        built.add(frozenset((names[u], names[v])))
    assert built == campus_edges()
    assert edges_in(a.hints[-1].body) == campus_edges()


def test_a_graph_is_directed_exactly_when_its_edges_are_arrows() -> None:
    a = activity(106)
    # One graph has no edge list, so the step from the symbol to the meaning starts here (#214 C4).
    unlisted = [item for item in a.config["left"] if not edges_in(item["label"])]
    assert [item["id"] for item in unlisted] == ["older"]
    assert right_label(a, "older") == "Directed"
    for item in a.config["left"]:
        if item in unlisted:
            continue
        edges = edges_in(item["label"])
        directed = all(isinstance(e, tuple) for e in edges)
        assert directed or all(isinstance(e, frozenset) for e in edges)
        assert right_label(a, item["id"]) == ("Directed" if directed else "Undirected")


def test_the_key_terms_cannot_be_matched_by_their_own_words() -> None:
    """102 paired "Data structure" with "… store data" and "Graph traversal" with "… of a graph",
    with no spare description, so the last pair was forced (#214 C6)."""
    a = activity(102)
    terms = {item["id"]: item["label"].lower() for item in a.config["left"]}
    for left in a.solution["pairs"]:
        label = right_label(a, left).lower()
        for word in re.findall(r"\w+", terms[left]):
            assert not re.search(rf"\b{word}", label), (terms[left], label)
    assert len(a.config["right"]) >= len(a.config["left"]) + 2
    assert any("chart" in r["label"] for r in a.config["right"])  # a graph is not a chart


def test_the_modelling_support_item_does_not_name_each_situations_nouns() -> None:
    """193's right options named their situation's nouns (taxi ranks, children, songs, puzzle
    pieces), so each could be matched by spotting a word (#214 C8)."""
    a = activity(193)
    nouns = ("taxi", "rank", "child", "invit", "song", "playlist", "jigsaw", "puzzle", "piece")
    for r in a.config["right"]:
        assert not any(n in r["label"].lower() for n in nouns), r["label"]
    assert len(a.config["right"]) > len(a.config["left"])
