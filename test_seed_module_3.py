"""Module 3 (Meet BFS) content checks.

Recomputes BFS on the module 3 graph scenarios and checks that every answer in the
fixture matches it. Convention: neighbours are taken in alphabetical order (FR-6.5) and
a vertex is marked visited when it joins the queue.
"""

import json
from collections import deque
from pathlib import Path
from typing import Any

import pytest

SEED_DIR = Path(__file__).resolve().parents[1] / "app" / "seed" / "module_3"

Row = dict[str, Any]


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((SEED_DIR / name).read_text(encoding="utf-8"))
    return data


MODULE = _load("module.json")
SCENARIOS: dict[str, dict[str, Any]] = {
    s["id"]: s for s in _load("scenarios.json")["scenarios"]
}
ACTIVITIES: dict[str, dict[str, Any]] = {a["id"]: a for a in MODULE["activities"]}


def adjacency(scenario: dict[str, Any]) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = {v["id"]: [] for v in scenario["vertices"]}
    for edge in scenario["edges"]:
        adj[edge["source"]].append(edge["target"])
        if not scenario["directed"]:
            adj[edge["target"]].append(edge["source"])
    return {vertex: sorted(neighbours) for vertex, neighbours in adj.items()}


def bfs_rows(scenario: dict[str, Any]) -> list[Row]:
    adj = adjacency(scenario)
    start = scenario["start_vertex"]
    queue: deque[str] = deque([start])
    visited = {start}
    order: list[str] = []
    rows: list[Row] = []
    while queue:
        current = queue.popleft()
        order.append(current)
        for neighbour in adj[current]:
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(neighbour)
        rows.append(
            {
                "current": current,
                "queue": list(queue),
                "visited": sorted(visited),
                "order": list(order),
            }
        )
    return rows


def distances(scenario: dict[str, Any]) -> dict[str, int]:
    adj = adjacency(scenario)
    start = scenario["start_vertex"]
    dist = {start: 0}
    queue: deque[str] = deque([start])
    while queue:
        vertex = queue.popleft()
        for neighbour in adj[vertex]:
            if neighbour not in dist:
                dist[neighbour] = dist[vertex] + 1
                queue.append(neighbour)
    return dist


def referenced_activity_ids() -> set[str]:
    ids: set[str] = set()
    for segment in MODULE["segments"]:
        for key in ("activity_id", "skip_check_activity_id"):
            if key in segment:
                ids.add(segment[key])
        for checkpoint in segment.get("video", {}).get("checkpoints", []):
            ids.add(checkpoint["activity_id"])
    return ids


CAMPUS = bfs_rows(SCENARIOS["campus"])


def test_module_metadata() -> None:
    assert MODULE["module"]["number"] == 3
    assert MODULE["module"]["objectives"] == [4, 5]
    positions = [segment["position"] for segment in MODULE["segments"]]
    assert positions == list(range(1, len(positions) + 1))


def test_every_activity_is_used_and_exists() -> None:
    referenced = referenced_activity_ids()
    assert referenced == set(ACTIVITIES)


@pytest.mark.parametrize("activity_id", sorted(ACTIVITIES))
def test_activity_has_four_hints(activity_id: str) -> None:
    assert len(ACTIVITIES[activity_id]["hints"]) == 4


@pytest.mark.parametrize("activity_id", sorted(ACTIVITIES))
def test_multiple_choice_answer_is_an_option(activity_id: str) -> None:
    activity = ACTIVITIES[activity_id]
    if activity["kind"] != "multiple_choice":
        pytest.skip("not multiple choice")
    option_ids = {option["id"] for option in activity["config"]["options"]}
    assert activity["answer"]["correct"] in option_ids
    wrong = option_ids - {activity["answer"]["correct"]}
    assert wrong <= set(activity["feedback"]), "every wrong option needs feedback"


def test_scenarios_referenced_exist() -> None:
    for activity in ACTIVITIES.values():
        scenario_id = activity["config"].get("scenario_id")
        if scenario_id is not None:
            assert scenario_id in SCENARIOS


def test_checkpoints_fall_inside_their_video() -> None:
    for segment in MODULE["segments"]:
        if segment["kind"] != "video":
            continue
        video = segment["video"]
        for checkpoint in video["checkpoints"]:
            assert 0 < checkpoint["at_seconds"] < video["duration_seconds"]


def test_campus_prediction_order() -> None:
    expected = ACTIVITIES["m3-predict-campus"]["answer"]["expected_order"]
    assert [row["current"] for row in CAMPUS] == expected


def test_campus_checkpoint_answers() -> None:
    assert adjacency(SCENARIOS["campus"])["A"] == ["C", "E"]  # m3-ck-one-step
    assert CAMPUS[0]["queue"] == ["C", "E"]  # m3-ck-who-leaves
    assert CAMPUS[1]["current"] == "C"
    assert CAMPUS[1]["queue"] == ["E", "B", "F"]  # m3-ck-who-joins, m3-skip-check
    assert CAMPUS[2]["queue"] == ["B", "F", "D"]  # m3-ck-already-queued


def test_campus_states_shown_in_checkpoints() -> None:
    who_leaves = ACTIVITIES["m3-ck-who-leaves"]["config"]["show_state"]
    assert who_leaves["queue"] == CAMPUS[0]["queue"]
    assert who_leaves["visited"] == CAMPUS[0]["visited"]
    already = ACTIVITIES["m3-ck-already-queued"]["config"]["show_state"]
    assert already["visited"] == CAMPUS[1]["visited"]


def test_transfer_task_distance() -> None:
    assert distances(SCENARIOS["campus"])["G"] == 3


def test_trace_table_answer_matches_bfs() -> None:
    activity = ACTIVITIES["m3-trace-practice"]
    scenario = SCENARIOS[activity["config"]["scenario_id"]]
    assert bfs_rows(scenario) == activity["answer"]["rows"]
    assert activity["config"]["rows"] == len(activity["answer"]["rows"])
