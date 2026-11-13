"""Module 2 (A graph in Python, #84): the code the module teaches really does what it says.

The code activities (three, and a support item from #173) are fill-in-the-blank: filled in with
their answers, the Graph class passes the tests below (the hidden tests from the module's design), and each token a wrong-answer
message is written for really breaks one of them, so the message describes a real mistake. Every
other answer (the dictionaries, the worked example's table, the closing task) is what the
finished class produces. Plus the content rules from issue #84: four hint levels on every
activity, and feedback for every wrong option.
"""

import json
import re
from collections import deque
from typing import Any

import pytest

from app.seed import ActivityFixture, FixtureFile, read_fixtures

CONTENT: FixtureFile = read_fixtures()
CAMPUS = next(g for g in CONTENT.graphs if g.id == 4)
MODULE = next(m for m in CONTENT.modules if m.id == 2)
ACTIVITIES = [a for a in CONTENT.activities if a.module_id == 2]
BLANK = re.compile(r"__(\d+)__")
DASH = "\N{EN DASH}"  # the content joins an undirected edge's ends with it
EDGE = re.compile(rf"\b([A-Z]) ?({DASH}|→) ?([A-Z])\b")

# The hidden tests from the module's design, per code activity. Each runs after the class.
TESTS = {
    205: [
        'g = Graph()\ng.add_vertex("A")\nassert g.adjacency == {"A": []}',
        'g = Graph()\ng.add_vertex("A")\ng.add_vertex("B")\nassert g.adjacency == {"A": [], "B": []}',
        'g = Graph()\ng.add_vertex("A")\ng.adjacency["A"].append("B")\ng.add_vertex("A")\n'
        'assert g.adjacency["A"] == ["B"]',
        'g = Graph()\ng.add_vertex("A")\ng.add_vertex("B")\ng.adjacency["A"].append("C")\n'
        'assert g.adjacency["B"] == []',
    ],
    206: [
        'g = Graph()\ng.add_vertex("A")\ng.add_vertex("C")\ng.add_edge("A", "C")\n'
        'assert g.adjacency == {"A": ["C"], "C": ["A"]}',
        'g = Graph()\ng.add_edge("A", "E")\nassert g.adjacency == {"A": ["E"], "E": ["A"]}',
        'g = Graph()\ng.add_edge("A", "C")\ng.add_edge("A", "E")\n'
        'assert g.adjacency["A"] == ["C", "E"]',
        # The campus: every walkway, so a vertex's earlier neighbours must survive a later edge.
        "g = Graph()\n"
        + "\n".join(
            f'g.add_edge("{u}", "{v}")' for u, v in ("AC", "AE", "BC", "BG", "CF", "DE", "EF")
        )
        + '\nassert g.adjacency == {"A": ["C", "E"], "B": ["C", "G"], "C": ["A", "B", "F"], '
        '"D": ["E"], "E": ["A", "D", "F"], "F": ["C", "E"], "G": ["B"]}',
    ],
    207: [
        'g = Graph(directed=True)\ng.add_edge("D", "G")\n'
        'assert g.adjacency == {"D": ["G"], "G": []}',
        'g = Graph()\ng.add_edge("A", "C")\nassert g.adjacency == {"A": ["C"], "C": ["A"]}',
        'g = Graph(directed=True)\ng.add_edge("A", "B")\ng.add_edge("B", "A")\n'
        'assert g.adjacency == {"A": ["B"], "B": ["A"]}',
        'g = Graph(directed=True)\ng.add_edge("A", "D")\ng.add_edge("D", "G")\n'
        'g.add_edge("G", "A")\nassert g.adjacency == {"A": ["D"], "D": ["G"], "G": ["A"]}',
    ],
    # The support item for objective 6 (#173): the whole class, with the worked example's calls.
    291: [
        'g = Graph()\ng.add_edge("P", "R")\ng.add_edge("R", "T")\n'
        'assert g.adjacency == {"P": ["R"], "R": ["P", "T"], "T": ["R"]}',
        'g = Graph(directed=True)\ng.add_edge("P", "R")\ng.add_edge("R", "T")\n'
        'assert g.adjacency == {"P": ["R"], "R": ["T"], "T": []}',
        'g = Graph()\ng.add_edge("K", "L")\ng.add_vertex("L")\ng.add_edge("L", "M")\n'
        'assert g.adjacency["L"] == ["K", "M"]',
    ],
}


def activity(activity_id: int) -> ActivityFixture:
    return next(a for a in ACTIVITIES if a.id == activity_id)


def chosen_label(activity_id: int) -> str:
    a = activity(activity_id)
    correct = a.solution["correct"]
    return str(next(o["label"] for o in a.config["options"] if o["id"] == correct))


def filled(a: ActivityFixture, **changes: str) -> str:
    """The activity's code with every blank filled with its answer, or with `changes[blank]`."""
    answers = {str(k): v for k, v in a.solution["answers"].items()} | changes
    return BLANK.sub(lambda m: answers[m.group(1)], a.config["code"])


def passes(code: str, tests: list[str]) -> bool:
    try:
        for test in tests:
            namespace: dict[str, Any] = {}
            exec(code, namespace)  # noqa: S102 - our own fixture code, in our own tests
            exec(test, namespace)  # noqa: S102
    except Exception:  # any error, recursion included, is a failing test
        return False
    return True


def graph_class() -> Any:
    """The finished Graph class: the last code activity, filled in."""
    namespace: dict[str, Any] = {}
    exec(filled(activity(207)), namespace)  # noqa: S102
    return namespace["Graph"]


def run(calls: str) -> dict[str, list[str]]:
    namespace: dict[str, Any] = {"Graph": graph_class()}
    exec(calls, namespace)  # noqa: S102
    adjacency: dict[str, list[str]] = namespace["g"].adjacency
    return adjacency


def test_every_activity_is_shown_once_and_every_objective_has_one() -> None:
    shown = [s.activity_id for s in MODULE.segments if s.activity_id is not None]
    skip_checks = [s.skip_check_activity_id for s in MODULE.segments if s.skip_check_activity_id]
    # The recall questions are asked before the segments (FR-2.4), not in one.
    recall = [a.id for a in ACTIVITIES if a.purpose == "retrieval"]
    assert recall == [201, 202]
    assert sorted(shown + skip_checks + recall) == sorted(a.id for a in ACTIVITIES)
    assert {a.objective_id for a in ACTIVITIES} == {None, 2, 6}


@pytest.mark.parametrize("a", ACTIVITIES, ids=lambda a: str(a.id))
def test_every_activity_has_four_hint_levels_and_the_last_gives_the_answer(
    a: ActivityFixture,
) -> None:
    assert [h.level for h in a.hints] == [1, 2, 3, 4]
    assert a.hints[-1].body.startswith("Answer:")


@pytest.mark.parametrize(
    "a", [a for a in ACTIVITIES if a.kind != "fill_in"], ids=lambda a: str(a.id)
)
def test_every_wrong_answer_has_feedback(a: ActivityFixture) -> None:
    if a.kind == "multiple_choice":
        wrong = {o["id"] for o in a.config["options"]} - {a.solution["correct"]}
    else:
        wrong = {item["id"] for item in a.config["left"]}
    assert set(a.solution["feedback"]) == wrong


@pytest.mark.parametrize("activity_id", sorted(TESTS))
def test_the_code_has_exactly_its_blanks(activity_id: int) -> None:
    a = activity(activity_id)
    assert sorted(int(n) for n in BLANK.findall(a.config["code"])) == a.config["blanks"]


@pytest.mark.parametrize("activity_id", sorted(TESTS))
def test_the_answers_make_working_code(activity_id: int) -> None:
    assert passes(filled(activity(activity_id)), TESTS[activity_id])


@pytest.mark.parametrize(
    ("activity_id", "blank", "token"),
    [
        (a.id, str(blank), token)
        for a in ACTIVITIES
        if a.kind == "fill_in"
        for blank, messages in a.solution["feedback"].items()
        for token in messages
    ],
)
def test_each_mistake_with_a_message_really_fails(activity_id: int, blank: str, token: str) -> None:
    assert not passes(filled(activity(activity_id), **{blank: token}), TESTS[activity_id])


def test_the_queue_recall_answer() -> None:
    queue = deque(["A", "B"])
    queue.append("C")
    queue.popleft()
    assert chosen_label(201) == ", ".join(queue)


def test_the_neighbours_recall_answer_is_the_campus() -> None:
    assert edges_in(activity(202).config["prompt"]) == {
        frozenset((e.source, e.target)) for e in CAMPUS.edges
    }
    neighbours = sorted(
        e.target if e.source == "E" else e.source
        for e in CAMPUS.edges
        if "E" in (e.source, e.target)
    )
    assert chosen_label(202) == ", ".join(neighbours[:-1]) + " and " + neighbours[-1]


def test_the_skip_check_answer() -> None:
    adjacency = run('g = Graph()\ng.add_edge("P", "Q")\ng.add_edge("Q", "R")')
    assert json.loads(chosen_label(203)) == adjacency


def edges_in(text: str) -> set[frozenset[str] | tuple[str, str]]:
    """The edges a text lists: an edge written with a dash is undirected, `A → C` directed."""
    return {(u, v) if arrow == "→" else frozenset((u, v)) for u, arrow, v in EDGE.findall(text)}


def test_each_graph_matches_the_dictionary_the_class_builds() -> None:
    a = activity(204)
    right = {r["id"]: json.loads(r["label"]) for r in a.config["right"]}
    for item in a.config["left"]:
        directed = "(directed)" in item["label"]
        calls = [f"g = Graph(directed={directed})"]
        for u, _, v in EDGE.findall(item["label"]):
            calls.append(f'g.add_edge("{u}", "{v}")')
        assert right[a.solution["pairs"][item["id"]]] == run("\n".join(calls)), item["id"]


def test_the_worked_example_rows_are_what_the_class_does() -> None:
    worked = next(s for s in MODULE.segments if s.kind == "worked_example")
    assert worked.skip_check_activity_id == 203
    rows = re.findall(r"^\| `(.+?)` \| `(.+?)` \|", worked.body, re.M)
    assert len(rows) == 5
    calls = []
    for call, after in rows:
        calls.append(call)
        assert run("\n".join(calls)) == json.loads(after), call
    arrows = re.search(r"`h\.add_edge\((.+?)\)` gives `(.+?)`", worked.body)
    assert arrows
    h = run(f"g = Graph(directed=True)\ng.add_edge({arrows.group(1)})")
    assert h == json.loads(arrows.group(2))


def test_the_closing_task_answer() -> None:
    prompt = activity(208).config["prompt"]
    *calls, printed = prompt.split("print? ")[1].removesuffix(".").split(", then ")
    assert printed == 'print(g.adjacency["D"])'
    adjacency = run("\n".join(calls))
    assert json.loads(chosen_label(208)) == adjacency["D"]


def test_the_add_edge_feedback_only_names_the_items_own_vertices() -> None:
    """207's feedback used to talk about a-c and D to G, which the item never mentions (#147)."""
    for messages in activity(207).solution["feedback"].values():
        for text in messages.values():
            assert not EDGE.search(text), text  # its vertices are a and b, never capitals


def test_hint_3_of_the_dictionaries_item_names_the_one_that_matches_nothing() -> None:
    """Hint 3 said "the fourth dictionary" matches nothing, but the fourth one shown is graph 3's
    answer (#214 C11). It now quotes the spare dictionary."""
    a = next(x for x in CONTENT.activities if x.id == 204)
    used = set(a.solution["pairs"].values())
    (spare,) = [r["label"] for r in a.config["right"] if r["id"] not in used]
    assert spare in a.hints[2].body
    assert "fourth" not in a.hints[2].body
