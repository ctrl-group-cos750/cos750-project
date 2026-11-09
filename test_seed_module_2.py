"""Module 2 (A graph in Python) content checks.

Runs every code activity's reference solution against its tests, checks that every faulty
implementation fails at least one hidden test (NFR-M5), and checks the content rules from
issue #84: retrieval questions, four hint levels, three-part feedback (result, reason,
next step) and a text description of every graph.

The code here is our own fixture content, so it runs in-process. Student code never runs
here; it goes through the code runner.
"""

import json
from collections import deque
from pathlib import Path
from typing import Any

import pytest

SEED_DIR = Path(__file__).resolve().parents[1] / "app" / "seed"
MODULE_DIR = SEED_DIR / "module_2"


def _load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


MODULE = _load(MODULE_DIR / "module.json")
SCENARIOS: dict[str, dict[str, Any]] = {
    s["id"]: s for s in _load(MODULE_DIR / "scenarios.json")["scenarios"]
}
ACTIVITIES: dict[str, dict[str, Any]] = {a["id"]: a for a in MODULE["activities"]}
CODE_ACTIVITIES = sorted(
    a["id"] for a in ACTIVITIES.values() if a["kind"] == "complete_code"
)
FEEDBACK_PARTS = {"result", "reason", "next_step"}


# --- helpers ----------------------------------------------------------------


def passes(code: str, test: dict[str, str]) -> bool:
    namespace: dict[str, Any] = {}
    try:
        exec(compile(code, "<solution>", "exec"), namespace)  # noqa: S102
        exec(compile(test["code"], f"<{test['name']}>", "exec"), namespace)  # noqa: S102
    except Exception:  # noqa: BLE001
        return False
    return True


def reference_graph(directed: bool = False) -> Any:
    namespace: dict[str, Any] = {}
    code = ACTIVITIES["m2-directed"]["answer"]["reference_solution"]
    exec(compile(code, "<reference>", "exec"), namespace)  # noqa: S102
    return namespace["Graph"](directed=directed)


def adjacency(scenario: dict[str, Any]) -> dict[str, list[str]]:
    graph = reference_graph(scenario["directed"])
    for vertex in scenario["vertices"]:
        graph.add_vertex(vertex["id"])
    for e in scenario["edges"]:
        graph.add_edge(e["source"], e["target"])
    result: dict[str, list[str]] = graph.adjacency
    return result


def option_value(activity_id: str) -> Any:
    activity = ACTIVITIES[activity_id]
    text = next(
        o["text"]
        for o in activity["config"]["options"]
        if o["id"] == activity["answer"]["correct"]
    )
    return json.loads(text.strip("`"))


def edge_label(scenario: dict[str, Any], e: dict[str, str]) -> str:
    arrow = " → " if scenario["directed"] else "–"
    return f"{e['source']}{arrow}{e['target']}"


# --- module structure -------------------------------------------------------


def test_module_metadata() -> None:
    meta = MODULE["module"]
    assert meta["number"] == 2
    assert meta["objectives"] == [2, 6]
    assert len(meta["goals"]) == len(meta["objectives"])  # FR-2.3
    positions = [s["position"] for s in MODULE["segments"]]
    assert positions == list(range(1, len(positions) + 1))


def test_opens_with_retrieval() -> None:  # FR-2.4
    opening = []
    for segment in MODULE["segments"]:
        activity = ACTIVITIES.get(segment.get("activity_id", ""))
        if activity is None or activity["purpose"] != "retrieval":
            break
        opening.append(activity)
    assert 1 <= len(opening) <= 2


def test_worked_example_has_skip_check() -> None:  # FR-8.2
    worked = [s for s in MODULE["segments"] if s["kind"] == "worked_example"]
    assert worked and all(s["skip_check_activity_id"] in ACTIVITIES for s in worked)


def test_every_activity_is_used() -> None:
    used: set[str] = set()
    for segment in MODULE["segments"]:
        for key in ("activity_id", "skip_check_activity_id"):
            if key in segment:
                used.add(segment[key])
        for checkpoint in segment.get("video", {}).get("checkpoints", []):
            assert 0 < checkpoint["at_seconds"] < segment["video"]["duration_seconds"]
            used.add(checkpoint["activity_id"])
    assert used == set(ACTIVITIES)


def test_every_objective_has_evidence() -> None:
    tagged = {a["objective_id"] for a in ACTIVITIES.values()} - {None}
    assert tagged == set(MODULE["module"]["objectives"])


# --- hints and feedback -----------------------------------------------------


@pytest.mark.parametrize("activity_id", sorted(ACTIVITIES))
def test_activity_has_four_hints(activity_id: str) -> None:
    hints = ACTIVITIES[activity_id]["hints"]
    assert len(hints) == 4
    assert hints[3].startswith("Answer:"), "level 4 is the worked solution"


@pytest.mark.parametrize("activity_id", sorted(ACTIVITIES))
def test_feedback_has_three_parts(activity_id: str) -> None:
    feedback = ACTIVITIES[activity_id]["feedback"]
    assert "correct" in feedback
    for key, message in feedback.items():
        assert set(message) == FEEDBACK_PARTS, f"{key} needs result, reason, next_step"
        assert all(message[part].strip() for part in FEEDBACK_PARTS)


@pytest.mark.parametrize("activity_id", sorted(ACTIVITIES))
def test_choice_answers_have_feedback(activity_id: str) -> None:
    activity = ACTIVITIES[activity_id]
    if activity["kind"] == "multiple_choice":
        options = {o["id"] for o in activity["config"]["options"]}
        assert activity["answer"]["correct"] in options
        assert options - {activity["answer"]["correct"]} <= set(activity["feedback"])
    elif activity["kind"] == "matching":
        left = {item["id"] for item in activity["config"]["left"]}
        right = {item["id"] for item in activity["config"]["right"]}
        assert set(activity["answer"]["pairs"]) == left
        assert set(activity["answer"]["pairs"].values()) <= right
        assert left <= set(activity["feedback"])
    else:
        pytest.skip("not a choice activity")


# --- code activities (NFR-M5) -----------------------------------------------


@pytest.mark.parametrize("activity_id", CODE_ACTIVITIES)
def test_reference_passes_every_test(activity_id: str) -> None:
    activity = ACTIVITIES[activity_id]
    tests = activity["config"]["example_tests"] + activity["answer"]["hidden_tests"]
    for test in tests:
        assert passes(activity["answer"]["reference_solution"], test), test["name"]


@pytest.mark.parametrize("activity_id", CODE_ACTIVITIES)
def test_every_faulty_version_fails_a_hidden_test(activity_id: str) -> None:
    answer = ACTIVITIES[activity_id]["answer"]
    assert answer["faulty_implementations"]
    for faulty in answer["faulty_implementations"]:
        results = [passes(faulty["code"], t) for t in answer["hidden_tests"]]
        assert not all(results), f"{faulty['name']} passes every hidden test"


@pytest.mark.parametrize("activity_id", CODE_ACTIVITIES)
def test_starter_code_runs_but_is_not_solved(activity_id: str) -> None:
    activity = ACTIVITIES[activity_id]
    starter = activity["config"]["starter_code"]
    compile(starter, "<starter>", "exec")
    assert not all(passes(starter, t) for t in activity["answer"]["hidden_tests"])


@pytest.mark.parametrize("activity_id", CODE_ACTIVITIES)
def test_every_hidden_test_has_feedback(activity_id: str) -> None:
    activity = ACTIVITIES[activity_id]
    names = [t["name"] for t in activity["answer"]["hidden_tests"]]
    assert len(names) == len(set(names))
    assert set(names) <= set(activity["feedback"])


# --- graphs -----------------------------------------------------------------


@pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
def test_description_lists_every_vertex_and_edge(scenario_id: str) -> None:
    scenario = SCENARIOS[scenario_id]
    text = scenario["description"]
    assert text.startswith("Directed" if scenario["directed"] else "Undirected")
    for vertex in scenario["vertices"]:
        assert vertex["label"] in text
        if "name" in vertex:
            assert vertex["name"] in text
    for e in scenario["edges"]:
        assert edge_label(scenario, e) in text
    assert f"{len(scenario['vertices'])} vertices" in text
    assert f"{len(scenario['edges'])} edges" in text


def test_every_scenario_is_used() -> None:
    used: set[str] = set()
    for activity in ACTIVITIES.values():
        config = activity["config"]
        if "scenario_id" in config:
            used.add(config["scenario_id"])
        used.update(item["scenario_id"] for item in config.get("left", []))
    used.add("m2-campus")  # built by the hidden test in m2-add-edge
    assert used == set(SCENARIOS)


@pytest.mark.parametrize(
    ("module", "scenario_id"),
    [("module_1", "m1-campus"), ("module_3", "campus"), ("module_1", "m1-shuttle")],
)
def test_graphs_match_other_modules(module: str, scenario_id: str) -> None:
    path = SEED_DIR / module / "scenarios.json"
    if not path.exists():
        pytest.skip(f"{module} not in this branch")
    other = {s["id"]: s for s in _load(path)["scenarios"]}[scenario_id]
    mine = SCENARIOS["m2-shuttle" if "shuttle" in scenario_id else "m2-campus"]
    assert adjacency(other) == adjacency(mine)


# --- answers ----------------------------------------------------------------


def test_queue_recall() -> None:
    queue = deque(["A", "B"])
    queue.append("C")
    queue.popleft()
    activity = ACTIVITIES["m2-recall-queue"]
    text = next(
        o["text"]
        for o in activity["config"]["options"]
        if o["id"] == activity["answer"]["correct"]
    )
    assert text == ", ".join(queue)


def test_neighbours_recall() -> None:
    neighbours = sorted(adjacency(SCENARIOS["m2-campus"])["E"])
    activity = ACTIVITIES["m2-recall-neighbours"]
    text = next(
        o["text"]
        for o in activity["config"]["options"]
        if o["id"] == activity["answer"]["correct"]
    )
    assert text == f"{', '.join(neighbours[:-1])} and {neighbours[-1]}"


def test_dictionary_checkpoints() -> None:
    assert option_value("m2-ck-dict") == adjacency(SCENARIOS["m2-corner"])
    assert option_value("m2-ck-directed") == adjacency(SCENARIOS["m2-shuttle"])


def test_skip_check() -> None:
    graph = reference_graph()
    graph.add_edge("P", "Q")
    graph.add_edge("Q", "R")
    assert option_value("m2-skip-check") == graph.adjacency


def test_matching_dictionaries() -> None:
    activity = ACTIVITIES["m2-match"]
    right = {
        item["id"]: json.loads(item["text"]) for item in activity["config"]["right"]
    }
    for item in activity["config"]["left"]:
        expected = adjacency(SCENARIOS[item["scenario_id"]])
        assert right[activity["answer"]["pairs"][item["id"]]] == expected
        others = [k for k, v in right.items() if v == expected]
        assert others == [activity["answer"]["pairs"][item["id"]]], "answer is unique"


def test_closing_output() -> None:
    graph = reference_graph(directed=True)
    for a, b in [("A", "D"), ("D", "G"), ("G", "A")]:
        graph.add_edge(a, b)
    assert option_value("m2-closing") == graph.adjacency["D"]
