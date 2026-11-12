"""Module 4 (Build BFS, #85): the BFS the module builds really works, and is the engine's.

The worked example's code is the reference. The Parsons answer is exactly its lines, and the two
fill-in activities, filled in with their answers, are exactly it too. Run on the student's own
Graph class (module 2's last activity, filled in), it passes the hidden tests from the module's
design, and every token a wrong-answer message is written for really fails one of them, so the
message describes a real mistake. Every BFS fact the module states (the recall order, the
adjacency list, the worked example's rows, the skip check, the closing task) is checked against
the engine (app/services/bfs.py) or the reference. Plus the content rules from issue #85: four
hint levels on every activity, and feedback for every wrong option.
"""

import json
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType
from typing import Any

import pytest
from parsons_orders import runnable_orders

from app.schemas.activities import ParsonsSolution
from app.schemas.graphs import GraphEdge, GraphScenarioOut
from app.seed import ActivityFixture, FixtureFile, read_fixtures
from app.services.bfs import run_bfs
from app.services.checking import check_activity

CONTENT: FixtureFile = read_fixtures()
CAMPUS = GraphScenarioOut(**next(g for g in CONTENT.graphs if g.id == 4).model_dump())
MODULE = next(m for m in CONTENT.modules if m.id == 4)
ACTIVITIES = [a for a in CONTENT.activities if a.module_id == 4]
WORKED = next(s for s in MODULE.segments if s.kind == "worked_example")
BLANK = re.compile(r"__(\d+)__")
DASH = "\N{EN DASH}"  # the content joins an undirected edge's ends with it
EDGE = re.compile(rf"\b([A-Z]) ?({DASH}|→) ?([A-Z])\b")
CODE_BLOCK = re.compile(r"```python\n(.+?)\n```", re.S)
STEP_BUDGET = 100_000  # lines a test may run: `queue[0]` never empties the queue


def graph_code(vertices: str, edges: list[str], directed: bool = False) -> str:
    """Builds a graph with the Graph class, as the design's tests do: every vertex, then every
    edge, in the order given."""
    lines = [f"g = Graph(directed={directed})"]
    lines += [f'g.add_vertex("{v}")' for v in vertices]
    lines += [f'g.add_edge("{e[0]}", "{e[1]}")' for e in edges]
    return "\n".join(lines) + "\n"


CAMPUS_CODE = graph_code("ABCDEFG", ["AC", "AE", "BC", "BG", "CF", "DE", "EF"])
TRIANGLE = graph_code("ABC", ["AB", "AC", "BC"])
SPLIT = graph_code("ABCD", ["AB", "CD"])
SHUTTLE = graph_code("ADG", ["AD", "DG", "GA"], directed=True)
WORKED_EXAMPLE = graph_code("PQRS", ["PQ", "PR", "QS"]) + (
    'assert bfs(g, "P") == ["P", "Q", "R", "S"]'
)

# The example and hidden tests from the module's design, per code activity.
TESTS = {
    405: [
        WORKED_EXAMPLE,
        TRIANGLE + 'order = bfs(g, "A")\nassert len(order) == len(set(order))',
        CAMPUS_CODE + 'assert bfs(g, "A") == ["A", "C", "E", "B", "F", "D", "G"]',
        SPLIT + 'assert bfs(g, "A") == ["A", "B"]',
        SHUTTLE + 'assert bfs(g, "A") == ["A", "D", "G"]',
    ],
    406: [
        WORKED_EXAMPLE,
        TRIANGLE + 'assert isinstance(bfs(g, "A"), list)',
        TRIANGLE + 'order = bfs(g, "A")\nassert len(order) == len(set(order))',
        CAMPUS_CODE + 'assert bfs(g, "A") == ["A", "C", "E", "B", "F", "D", "G"]',
        # Edges added out of alphabetical order: BFS still takes B, C, D.
        graph_code("ABCD", ["AD", "AB", "AC"]) + 'assert bfs(g, "A") == ["A", "B", "C", "D"]',
        graph_code("A", []) + 'assert bfs(g, "A") == ["A"]',
        SPLIT + 'assert bfs(g, "A") == ["A", "B"]',
        SHUTTLE + 'assert bfs(g, "A") == ["A", "D", "G"]',
        CAMPUS_CODE + 'assert bfs(g, "D") == ["D", "E", "A", "F", "C", "B", "G"]',
    ],
}


def activity(activity_id: int) -> ActivityFixture:
    return next(a for a in CONTENT.activities if a.id == activity_id)


def chosen_label(activity_id: int) -> str:
    a = activity(activity_id)
    correct = a.solution["correct"]
    return str(next(o["label"] for o in a.config["options"] if o["id"] == correct))


def filled(a: ActivityFixture, **changes: str) -> str:
    """The activity's code with every blank filled with its answer, or with `changes[blank]`."""
    answers = {str(k): v for k, v in a.solution["answers"].items()} | changes
    return BLANK.sub(lambda m: answers[m.group(1)], a.config["code"])


def reference() -> str:
    """The worked example's code: the BFS the whole module builds."""
    match = CODE_BLOCK.search(WORKED.body)
    assert match
    return match.group(1)


def graph_class() -> Any:
    """The student's own Graph class: module 2's last code activity, filled in."""
    namespace: dict[str, Any] = {}
    exec(filled(activity(207)), namespace)  # noqa: S102 - our own fixture code
    return namespace["Graph"]


@contextmanager
def step_budget() -> Iterator[None]:
    """Stops code that runs more than STEP_BUDGET lines, so an endless loop fails the test."""
    steps = 0

    def tracer(frame: FrameType, event: str, arg: Any) -> Any:
        nonlocal steps
        if event == "line":
            steps += 1
            if steps > STEP_BUDGET:
                raise TimeoutError("the code never finishes")
        return tracer

    previous = sys.gettrace()
    sys.settrace(tracer)
    try:
        yield
    finally:
        sys.settrace(previous)


def passes(code: str, tests: list[str]) -> bool:
    try:
        for test in tests:
            namespace: dict[str, Any] = {"Graph": graph_class()}
            with step_budget():
                exec(code, namespace)  # noqa: S102 - our own fixture code, in our own tests
                exec(test, namespace)  # noqa: S102
    except Exception:  # any error, an endless loop included, is a failing test
        return False
    return True


def run(code: str, setup: str, start: str) -> list[str]:
    """`code`'s bfs from `start`, on the graph `setup` builds with the Graph class."""
    namespace: dict[str, Any] = {"Graph": graph_class()}
    exec(code + "\n" + setup, namespace)  # noqa: S102
    order: list[str] = namespace["bfs"](namespace["g"], start)
    return order


def edges_in(text: str) -> list[tuple[str, str, bool]]:
    """The edges a text lists, in order: an edge written with a dash is undirected, `A → C`
    directed."""
    return [(u, v, arrow == "→") for u, arrow, v in EDGE.findall(text)]


def setup_from(text: str) -> str:
    """Graph-building code for the edges a text lists."""
    edges = edges_in(text)
    directed = any(d for _, _, d in edges)
    calls = [f"g = Graph(directed={directed})"]
    calls += [f'g.add_edge("{u}", "{v}")' for u, v, _ in edges]
    return "\n".join(calls)


def test_every_activity_is_shown_once_and_every_objective_has_one() -> None:
    shown = [s.activity_id for s in MODULE.segments if s.activity_id is not None]
    skip_checks = [s.skip_check_activity_id for s in MODULE.segments if s.skip_check_activity_id]
    # The recall questions are asked before the segments (FR-2.4), not in one.
    recall = [a.id for a in ACTIVITIES if a.purpose == "retrieval"]
    assert recall == [401, 402]
    assert sorted(shown + skip_checks + recall) == sorted(a.id for a in ACTIVITIES)
    assert {a.objective_id for a in ACTIVITIES} == {2, 5, 6}


def test_support_fades_parsons_then_fill_in_then_most_lines_blank() -> None:  # ID document §7.4
    # Everyone's path: a support segment (#172, #173) is only for a student who struggles.
    shown = [
        activity(s.activity_id)
        for s in MODULE.segments
        if s.activity_id is not None and s.support_for is None
    ]
    code = [a for a in shown if a.kind in ("parsons", "fill_in")]
    assert [a.id for a in code] == [404, 405, 406]
    assert code[0].kind == "parsons"
    assert len(code[1].config["blanks"]) < len(code[2].config["blanks"])
    assert WORKED.skip_check_activity_id == 403
    assert MODULE.segments.index(WORKED) < MODULE.segments.index(
        next(s for s in MODULE.segments if s.activity_id == 404)
    )


@pytest.mark.parametrize("a", ACTIVITIES, ids=lambda a: str(a.id))
def test_every_activity_has_four_hint_levels_and_the_last_gives_the_answer(
    a: ActivityFixture,
) -> None:
    assert [h.level for h in a.hints] == [1, 2, 3, 4]
    assert a.hints[-1].body.startswith("Answer:")


@pytest.mark.parametrize(
    "a", [a for a in ACTIVITIES if a.kind == "multiple_choice"], ids=lambda a: str(a.id)
)
def test_every_wrong_option_has_feedback(a: ActivityFixture) -> None:
    wrong = {o["id"] for o in a.config["options"]} - {a.solution["correct"]}
    assert set(a.solution["feedback"]) == wrong


def test_the_reference_is_the_engine_on_every_graph_from_every_start() -> None:
    for g in CONTENT.graphs:
        setup = graph_code("".join(g.vertices), [e.source + e.target for e in g.edges], g.directed)
        for start in g.vertices:
            scenario = GraphScenarioOut(**g.model_dump() | {"start_vertex": start})
            assert run(reference(), setup, start) == run_bfs(scenario).order, (g.id, start)


def test_the_parsons_answer_is_the_worked_examples_code() -> None:
    a = activity(404)
    order = ParsonsSolution.model_validate(a.solution).first_order()
    text = {line["id"]: line["text"] for line in a.config["lines"]}
    assert sorted(text) == sorted(order)  # every line is used, no distractors
    assert [text[i] for i in order] == [line for line in reference().split("\n") if line.strip()]
    shown = [line["id"] for line in a.config["lines"]]
    assert not check_activity("parsons", a.config, a.solution, {"order": shown}).correct  # shuffled


def test_the_parsons_problem_accepts_exactly_the_orders_that_work() -> None:
    """Every order of the lines Python can run is tried on the design's tests: each the checker
    accepts passes, and each that passes is accepted (FR-5.4, #145), with two deliberate
    exceptions that also run. The import after the function: the lessons and PEP 8 put imports
    first. order.append(v) after the neighbour loop: module 3 says a vertex joins the order when
    it leaves the queue, and the worked example writes it straight after popleft()."""
    a = activity(404)
    text = {line["id"]: line["text"] for line in a.config["lines"]}
    working, accepted = [], []
    for order in runnable_orders(text):
        if passes("\n".join(text[i] for i in order), TESTS[406]):
            working.append(order)
        if check_activity("parsons", a.config, a.solution, {"order": order}).correct:
            accepted.append(order)
    assert accepted == [order for order in working if conventional(order, text)]
    # The three starting values (3! orders) x visited.add/queue.append (2); the exceptions double
    # it twice: the import first or last, order.append(v) before or after the neighbour loop.
    assert len(accepted) == 12
    assert len(working) == 48


def conventional(order: list[int], text: dict[int, str]) -> bool:
    """The import comes first, and order.append(v) straight after the vertex leaves the queue."""
    lines = [text[i].strip() for i in order]
    after_dequeue = lines[next(n for n, t in enumerate(lines) if ".popleft()" in t) + 1]
    return lines[0].startswith("from ") and after_dequeue.startswith("order.append(")


@pytest.mark.parametrize("activity_id", sorted(TESTS))
def test_the_code_has_exactly_its_blanks(activity_id: int) -> None:
    a = activity(activity_id)
    assert sorted(int(n) for n in BLANK.findall(a.config["code"])) == a.config["blanks"]


@pytest.mark.parametrize("activity_id", sorted(TESTS))
def test_the_answers_make_the_worked_examples_code(activity_id: int) -> None:
    code_lines = [
        line.split("  #")[0].rstrip()
        for line in filled(activity(activity_id)).split("\n")
        if not line.strip().startswith("#")
    ]
    assert "\n".join(code_lines) == reference()


@pytest.mark.parametrize("activity_id", sorted(TESTS))
def test_the_answers_pass_the_hidden_tests(activity_id: int) -> None:
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


def test_the_bfs_order_recall_answer_is_the_engines_on_the_campus() -> None:
    prompt = activity(401).config["prompt"]
    assert {frozenset((u, v)) for u, v, _ in edges_in(prompt)} == {
        frozenset((e.source, e.target)) for e in CAMPUS.edges
    }
    assert chosen_label(401) == ", ".join(run_bfs(CAMPUS).order)


def test_the_adjacency_recall_answer_is_what_the_class_builds() -> None:
    prompt = activity(402).config["prompt"]
    assert [(e.source, e.target) for e in CAMPUS.edges] == [(u, v) for u, v, _ in edges_in(prompt)]
    namespace: dict[str, Any] = {"Graph": graph_class()}
    exec(setup_from(prompt), namespace)  # noqa: S102
    assert json.loads(chosen_label(402)) == namespace["g"].adjacency["C"]


def test_the_worked_example_rows_are_the_engines_steps() -> None:
    edges = edges_in(WORKED.body.split("**Running it**")[1])
    scenario = GraphScenarioOut(
        id=0,
        name="",
        directed=False,
        vertices=sorted({v for u, w, _ in edges for v in (u, w)}),
        edges=[GraphEdge(source=u, target=v) for u, v, _ in edges],
        start_vertex="P",
    )
    rows = re.findall(r"^\| (\w) \| ([\w, ]+) \| ([\w, ()]+) \| ([\w, ]+) \|$", WORKED.body, re.M)
    steps = run_bfs(scenario).steps
    assert len(rows) == len(steps) == 4
    found = [scenario.start_vertex]
    for (v, order, queue, visited), step in zip(rows, steps, strict=True):
        found += step.discovered
        assert v == step.visited_vertex
        assert order.split(", ") == step.order, v
        assert ([] if queue == "(empty)" else queue.split(", ")) == step.queue, v
        assert visited.split(", ") == found, v
    result = re.search(r"\*\*Result:\*\* `(.+?)`", WORKED.body)
    assert result
    assert json.loads(result.group(1)) == run_bfs(scenario).order


def test_the_skip_check_answer() -> None:
    prompt = activity(403).config["prompt"]
    assert json.loads(chosen_label(403)) == run(reference(), setup_from(prompt), "W")


def test_the_closing_task_answer() -> None:
    prompt = activity(407).config["prompt"]
    assert all(directed for _, _, directed in edges_in(prompt))
    assert json.loads(chosen_label(407)) == run(reference(), setup_from(prompt), "D")
