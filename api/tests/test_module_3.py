"""Module 3 (Meet BFS, #27): every BFS fact the content states is the engine's.

The lesson, the visualiser and the trace-table checker all use one engine (app/services/bfs.py),
so these tests run it and compare: if the content or a graph changes, a stale answer, hint or
worked-example row fails here instead of teaching students something the checker marks wrong.
"""

import re

from app.schemas.graphs import BfsStep, GraphScenarioOut
from app.seed import ActivityFixture, FixtureFile, read_fixtures
from app.services.bfs import run_bfs

CONTENT: FixtureFile = read_fixtures()
CAMPUS = GraphScenarioOut(**next(g for g in CONTENT.graphs if g.id == 4).model_dump())
MODULE = next(m for m in CONTENT.modules if m.id == 3)


def activity(activity_id: int) -> ActivityFixture:
    return next(a for a in CONTENT.activities if a.id == activity_id)


def chosen_label(activity_id: int) -> str:
    a = activity(activity_id)
    correct = a.solution["correct"]
    return str(next(o["label"] for o in a.config["options"] if o["id"] == correct))


def steps(scenario: GraphScenarioOut) -> list[BfsStep]:
    return run_bfs(scenario).steps


def test_the_campus_order_the_module_states_is_the_engines() -> None:
    assert run_bfs(CAMPUS).order == ["A", "C", "E", "B", "F", "D", "G"]
    worked = next(s for s in MODULE.segments if s.kind == "worked_example")
    assert "**A, C, E, B, F, D, G**" in worked.body


def test_the_worked_example_rows_are_the_engines_steps() -> None:
    worked = next(s for s in MODULE.segments if s.kind == "worked_example")
    rows = re.findall(
        r"^\| (\d) \| (\w) \| ([\w, ]+) \| ([\w, ]+) \| ([\w, ]+) \|$", worked.body, re.M
    )
    assert len(rows) == 3
    for (n, current, queue, visited, order), step in zip(rows, steps(CAMPUS), strict=False):
        assert current == step.visited_vertex, f"row {n}"
        assert queue.split(", ") == step.queue, f"row {n}"
        assert visited.split(", ") == step.visited, f"row {n}"
        assert order.split(", ") == step.order, f"row {n}"


def test_the_skip_check_answer_is_the_queue_after_c() -> None:
    after_c = next(s for s in steps(CAMPUS) if s.visited_vertex == "C")
    assert chosen_label(314) == ", ".join(after_c.queue) == "E, B, F"


def test_the_closing_task_answer_is_the_fewest_walkways_from_a_to_g() -> None:
    # Who discovered whom: follow G back to A.
    found_by = {v: s.visited_vertex for s in steps(CAMPUS) for v in s.discovered}
    path = ["G"]
    while path[-1] != CAMPUS.start_vertex:
        path.append(found_by[path[-1]])
    assert path[::-1] == ["A", "C", "B", "G"]
    assert chosen_label(316) == str(len(path) - 1)


def test_the_trace_tables_last_hint_is_the_engines_answer() -> None:
    trace = activity(315)
    graph = GraphScenarioOut(id=0, name="", **trace.config)
    result = run_bfs(graph)
    assert result.order == ["B", "A", "D", "C", "E"]
    last = trace.hints[-1].body
    assert "B, A, D, C, E" in last
    queues = ", ".join("[" + ", ".join(s.queue) + "]" for s in result.steps)
    assert queues in last


def test_the_visualiser_link_opens_the_campus_graph() -> None:
    predict = next(s for s in MODULE.segments if s.title.startswith("Your turn: predict"))
    assert f"(/graphs/{CAMPUS.id})" in predict.body
