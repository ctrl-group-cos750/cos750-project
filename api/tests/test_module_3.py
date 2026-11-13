"""Module 3 (Meet BFS, #27): every BFS fact the content states is the engine's.

The lesson, the visualiser and the trace-table checker all use one engine (app/services/bfs.py),
so these tests run it and compare: if the content or a graph changes, a stale answer, hint or
worked-example row fails here instead of teaching students something the checker marks wrong.
"""

import json
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


def found_by(scenario: GraphScenarioOut) -> dict[str, str]:
    return {v: s.visited_vertex for s in steps(scenario) for v in s.discovered}


def route_back(scenario: GraphScenarioOut, goal: str) -> list[str]:
    """Follow "found by" back from the goal to the start, as the lesson teaches."""
    back, path = found_by(scenario), [goal]
    while path[-1] != scenario.start_vertex:
        path.append(back[path[-1]])
    return path[::-1]


FROM_E = CAMPUS.model_copy(update={"start_vertex": "E"})


def test_the_closing_task_answer_is_the_route_bfs_records_from_e_to_b() -> None:
    """316 asked module 1's opening question again, A to G, whose answer module 1's video, module
    3's video and worked example 320 had all given (#214 C3). It now starts at E and asks for the
    route to B, which turns on the tie-break: A leaves the queue before F, so A finds C."""
    path = route_back(FROM_E, "B")
    assert path == ["E", "A", "C", "B"]
    assert chosen_label(316) == f"{' → '.join(path)}: {len(path) - 1} walkways"
    assert activity(316).hints[-1].body == f"Answer: {' → '.join(path)}, {len(path) - 1} walkways."
    # The tempting route is real and as short, but it isn't the one BFS records.
    labels = {o["id"]: o["label"] for o in activity(316).config["options"]}
    assert labels["f"] == "E → F → C → B: 3 walkways"
    assert {"F", "C"} in [{e.source, e.target} for e in CAMPUS.edges]
    assert {"E", "C"} not in [{e.source, e.target} for e in CAMPUS.edges]  # option g's walkway


def test_the_practice_before_the_closing_task_does_not_walk_its_route() -> None:
    """317, two items before 316, walked D → E → A → C → B → G in its explanation, feedback and
    hints: 316's answer, E → A → C → B, read straight off it (round 2 review of #215, content 6).
    317 now starts at F, and its answer is the engine's."""
    path = route_back(CAMPUS.model_copy(update={"start_vertex": "F"}), "G")
    assert chosen_label(317) == str(len(path) - 1)
    assert activity(317).hints[-1].body == f"Answer: {len(path) - 1} walkways, {' → '.join(path)}."
    a = activity(317)
    shown = json.dumps([a.config, a.solution, [h.body for h in a.hints]], ensure_ascii=False)
    answer = route_back(FROM_E, "B")
    for u, v, w in zip(answer, answer[1:], answer[2:], strict=False):
        assert f"{u} → {v} → {w}" not in shown  # no two steps of 316's route, either way round
        assert f"{w} → {v} → {u}" not in shown
    assert "A found C" not in shown  # 316's tie-break


def test_when_bfs_fits_reasons_share_no_word_with_their_situations() -> None:
    """313 could be matched by keyword: "time" in a situation and its reason, "two" friends and
    "two steps" (round 2 review of #215, content 10)."""
    a = activity(313)

    def words(text: str) -> set[str]:
        return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 4}

    reasons = {r["id"]: r["label"] for r in a.config["right"]}
    for situation in a.config["left"]:
        reason = reasons[a.solution["pairs"][situation["id"]]]
        assert not words(situation["label"]) & words(reason), (situation["label"], reason)


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


def test_when_bfs_fits_cannot_be_done_by_elimination() -> None:
    """313 had three situations and three reasons, one of them the only "Not a fit" (#147)."""
    a = activity(313)
    pairs = a.solution["pairs"]
    unused = {r["id"] for r in a.config["right"]} - set(pairs.values())
    assert unused  # reasons that fit no situation
    assert len(set(pairs.values())) < len(pairs)  # and one that fits two
    assert sum(r["label"].startswith("Not a fit") for r in a.config["right"]) >= 2
