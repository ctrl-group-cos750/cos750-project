"""Module 1 (What is a graph?) content checks.

Checks every answer against the graph scenarios, and the content rules from issue #83:
four hint levels and three-part feedback (result, reason, next step) on every activity,
and a text description of every graph that lists all its vertices and edges.
"""

import json
from collections import deque
from pathlib import Path
from typing import Any

import pytest

SEED_DIR = Path(__file__).resolve().parents[1] / "app" / "seed"
MODULE_DIR = SEED_DIR / "module_1"


def _load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


MODULE = _load(MODULE_DIR / "module.json")
SCENARIOS: dict[str, dict[str, Any]] = {
    s["id"]: s for s in _load(MODULE_DIR / "scenarios.json")["scenarios"]
}
ACTIVITIES: dict[str, dict[str, Any]] = {a["id"]: a for a in MODULE["activities"]}
FEEDBACK_PARTS = {"result", "reason", "next_step"}


def edge_key(scenario: dict[str, Any], source: str, target: str) -> tuple[str, ...]:
    if scenario["directed"]:
        return (source, target)
    return tuple(sorted((source, target)))


def edge_set(scenario: dict[str, Any]) -> set[tuple[str, ...]]:
    return {edge_key(scenario, e["source"], e["target"]) for e in scenario["edges"]}


def edge_label(scenario: dict[str, Any], source: str, target: str) -> str:
    return f"{source} → {target}" if scenario["directed"] else f"{source}–{target}"


def distance(scenario: dict[str, Any], start: str, goal: str) -> int:
    adj: dict[str, list[str]] = {v["id"]: [] for v in scenario["vertices"]}
    for e in scenario["edges"]:
        adj[e["source"]].append(e["target"])
        if not scenario["directed"]:
            adj[e["target"]].append(e["source"])
    dist = {start: 0}
    queue: deque[str] = deque([start])
    while queue:
        vertex = queue.popleft()
        for neighbour in sorted(adj[vertex]):
            if neighbour not in dist:
                dist[neighbour] = dist[vertex] + 1
                queue.append(neighbour)
    return dist[goal]


def referenced_activity_ids() -> set[str]:
    ids: set[str] = set()
    for segment in MODULE["segments"]:
        for key in ("activity_id", "skip_check_activity_id"):
            if key in segment:
                ids.add(segment[key])
        for checkpoint in segment.get("video", {}).get("checkpoints", []):
            ids.add(checkpoint["activity_id"])
    return ids


# --- module structure -------------------------------------------------------


def test_module_metadata() -> None:
    meta = MODULE["module"]
    assert meta["number"] == 1
    assert meta["objectives"] == [1, 2, 3]
    assert len(meta["goals"]) == len(meta["objectives"])  # FR-2.3
    positions = [segment["position"] for segment in MODULE["segments"]]
    assert positions == list(range(1, len(positions) + 1))


def test_opens_with_campus_puzzle() -> None:
    first = MODULE["segments"][0]
    assert first["activity_id"] == "m1-hook"  # Gagne event 1, before any terms


def test_worked_example_has_skip_check() -> None:  # FR-8.2
    worked = [s for s in MODULE["segments"] if s["kind"] == "worked_example"]
    assert worked and all(s["skip_check_activity_id"] in ACTIVITIES for s in worked)


def test_every_activity_is_used_and_exists() -> None:
    assert referenced_activity_ids() == set(ACTIVITIES)


def test_every_objective_has_evidence() -> None:
    tagged = {a["objective_id"] for a in ACTIVITIES.values()}
    assert tagged == set(MODULE["module"]["objectives"])


def test_checkpoints_fall_inside_their_video() -> None:
    for segment in MODULE["segments"]:
        if segment["kind"] == "video":
            video = segment["video"]
            for checkpoint in video["checkpoints"]:
                assert 0 < checkpoint["at_seconds"] < video["duration_seconds"]


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
def test_multiple_choice_answer_and_feedback(activity_id: str) -> None:
    activity = ACTIVITIES[activity_id]
    if activity["kind"] != "multiple_choice":
        pytest.skip("not multiple choice")
    option_ids = {option["id"] for option in activity["config"]["options"]}
    correct = activity["answer"]["correct"]
    assert correct in option_ids
    assert option_ids - {correct} <= set(activity["feedback"])


@pytest.mark.parametrize("activity_id", sorted(ACTIVITIES))
def test_matching_answer_and_feedback(activity_id: str) -> None:
    activity = ACTIVITIES[activity_id]
    if activity["kind"] != "matching":
        pytest.skip("not matching")
    left = {item["id"] for item in activity["config"]["left"]}
    right = {item["id"] for item in activity["config"]["right"]}
    pairs = activity["answer"]["pairs"]
    assert set(pairs) == left
    assert set(pairs.values()) <= right
    assert len(set(pairs.values())) == len(pairs), "each answer used once"
    assert left <= set(activity["feedback"])


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
        assert edge_label(scenario, e["source"], e["target"]) in text
    assert f"{len(scenario['vertices'])} vertices" in text
    assert f"{len(scenario['edges'])} edges" in text


def test_every_scenario_is_used() -> None:
    used: set[str] = set()
    for activity in ACTIVITIES.values():
        config = activity["config"]
        if "scenario_id" in config:
            used.add(config["scenario_id"])
        used.update(config.get("scenario_ids", []))
    assert used == set(SCENARIOS)


def test_campus_matches_module_3() -> None:
    other = SEED_DIR / "module_3" / "scenarios.json"
    if not other.exists():
        pytest.skip("module 3 not in this branch")
    module_3 = {s["id"]: s for s in _load(other)["scenarios"]}["campus"]
    campus = SCENARIOS["m1-campus"]
    assert [v["id"] for v in campus["vertices"]] == [
        v["id"] for v in module_3["vertices"]
    ]
    assert edge_set(campus) == edge_set(module_3)


# --- answers ----------------------------------------------------------------


def test_hook_answer_is_shortest_route() -> None:
    hook = ACTIVITIES["m1-hook"]
    campus = SCENARIOS[hook["config"]["scenario_id"]]
    assert int(hook["answer"]["correct"]) == distance(campus, "A", "G")


def test_count_checkpoint() -> None:
    campus = SCENARIOS["m1-campus"]
    activity = ACTIVITIES["m1-ck-count"]
    text = next(
        o["text"]
        for o in activity["config"]["options"]
        if o["id"] == activity["answer"]["correct"]
    )
    expected = f"{len(campus['vertices'])} vertices and {len(campus['edges'])} edges"
    assert text == expected


def test_skip_check_answer() -> None:
    graph = SCENARIOS["m1-skip"]
    degree = {v["id"]: 0 for v in graph["vertices"]}
    for e in graph["edges"]:
        degree[e["source"]] += 1
        degree[e["target"]] += 1
    busiest = max(degree, key=lambda v: degree[v])
    activity = ACTIVITIES["m1-skip-check"]
    text = next(
        o["text"]
        for o in activity["config"]["options"]
        if o["id"] == activity["answer"]["correct"]
    )
    assert text == f"{len(graph['edges'])} edges; {busiest} has the most neighbours"


def test_label_answers_match_markers() -> None:
    activity = ACTIVITIES["m1-label"]
    graph = SCENARIOS[activity["config"]["scenario_id"]]
    options = set(activity["config"]["label_options"])
    for marker in activity["config"]["markers"]:
        target = marker["target"]
        if target["type"] == "vertex":
            assert target["id"] in {v["id"] for v in graph["vertices"]}
            expected = f"Vertex {target['id']}"
        else:
            key = edge_key(graph, target["source"], target["target"])
            assert key in edge_set(graph)
            expected = f"Edge {target['source']}–{target['target']}"
        assert activity["answer"]["labels"][str(marker["marker"])] == expected
        assert expected in options


def test_build_answer_is_the_campus() -> None:
    activity = ACTIVITIES["m1-build"]
    campus = SCENARIOS[activity["config"]["scenario_id"]]
    answer = activity["answer"]
    assert set(answer["vertices"]) == {v["id"] for v in campus["vertices"]}
    assert {edge_key(campus, a, b) for a, b in answer["edges"]} == edge_set(campus)
    for e in campus["edges"]:  # the walkway list in the prompt matches the graph
        assert f"({e['source']}) –" in activity["prompt"]
        assert f"({e['target']})" in activity["prompt"]
    assert activity["prompt"].count(") – ") == len(campus["edges"])


def test_oneway_checkpoint() -> None:
    shuttle = SCENARIOS["m1-shuttle"]
    assert shuttle["directed"]
    assert ("A", "D") in edge_set(shuttle)
    assert ("D", "A") not in edge_set(shuttle)


def test_classify_answers_match_graphs() -> None:
    activity = ACTIVITIES["m1-classify"]
    classes = activity["answer"]["classes"]
    assert set(classes) == set(activity["config"]["scenario_ids"])
    for scenario_id, label in classes.items():
        directed = SCENARIOS[scenario_id]["directed"]
        assert label == ("directed" if directed else "undirected")
    assert set(classes.values()) == {"directed", "undirected"}
