"""Module 4 (Write BFS) content checks.

Runs every code activity's reference solution against its tests, checks that every faulty
implementation fails at least one hidden test (NFR-M5), checks that every accepted Parsons
order really is a working BFS, and checks the content rules from issue #85: fading support,
retrieval questions, four hint levels, three-part feedback (result, reason, next step) and a
text description of every graph.

The code here is our own fixture content, so it runs in-process with a time limit. Student
code never runs here; it goes through the code runner.
"""

import itertools
import json
import signal
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

SEED_DIR = Path(__file__).resolve().parents[1] / "app" / "seed"
MODULE_DIR = SEED_DIR / "module_4"


def _load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


MODULE = _load(MODULE_DIR / "module.json")
SCENARIOS: dict[str, dict[str, Any]] = {
    s["id"]: s for s in _load(MODULE_DIR / "scenarios.json")["scenarios"]
}
ACTIVITIES: dict[str, dict[str, Any]] = {a["id"]: a for a in MODULE["activities"]}
CODE_KINDS = {"complete_code", "write_code"}
CODE_ACTIVITIES = sorted(
    a["id"] for a in ACTIVITIES.values() if a["kind"] in CODE_KINDS
)
PARSONS = ACTIVITIES["m4-parsons"]
WRITE = ACTIVITIES["m4-write"]
FEEDBACK_PARTS = {"result", "reason", "next_step"}


# --- helpers ----------------------------------------------------------------


@contextmanager
def time_limit(seconds: int) -> Iterator[None]:
    def stop(signum: int, frame: Any) -> None:
        raise TimeoutError

    previous = signal.signal(signal.SIGALRM, stop)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def passes(provided: str, code: str, test: dict[str, str]) -> bool:
    namespace: dict[str, Any] = {}
    try:
        with time_limit(2):
            exec(compile(provided + "\n" + code, "<solution>", "exec"), namespace)  # noqa: S102
            exec(compile(test["code"], f"<{test['name']}>", "exec"), namespace)  # noqa: S102
    except Exception:  # noqa: BLE001
        return False
    return True


def all_pass(code: str) -> bool:
    provided = WRITE["config"]["provided_code"]
    tests = WRITE["config"]["example_tests"] + WRITE["answer"]["hidden_tests"]
    return all(passes(provided, code, test) for test in tests)


def bfs_order(scenario: dict[str, Any], start: str) -> list[str]:
    adj: dict[str, list[str]] = {v["id"]: [] for v in scenario["vertices"]}
    for e in scenario["edges"]:
        adj[e["source"]].append(e["target"])
        if not scenario["directed"]:
            adj[e["target"]].append(e["source"])
    visited, queue, order = {start}, deque([start]), []
    while queue:
        vertex = queue.popleft()
        order.append(vertex)
        for n in sorted(adj[vertex]):
            if n not in visited:
                visited.add(n)
                queue.append(n)
    return order


def correct_option(activity_id: str) -> str:
    activity = ACTIVITIES[activity_id]
    text: str = next(
        o["text"]
        for o in activity["config"]["options"]
        if o["id"] == activity["answer"]["correct"]
    )
    return text


def parsons_code(order: list[str]) -> str:
    lines = {line["id"]: line["code"] for line in PARSONS["config"]["lines"]}
    return "\n".join(lines[i] for i in order) + "\n"


def accepted_orders() -> Iterator[list[str]]:
    order: list[str] = PARSONS["answer"]["order"]
    groups: list[list[str]] = PARSONS["answer"]["interchangeable"]
    for choice in itertools.product(*(itertools.permutations(g) for g in groups)):
        result = list(order)
        for group, perm in zip(groups, choice, strict=True):
            start = result.index(group[0])
            result[start : start + len(group)] = perm
        yield result


# --- module structure -------------------------------------------------------


def test_module_metadata() -> None:
    meta = MODULE["module"]
    assert meta["number"] == 4
    assert meta["objectives"] == [6]
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
    assert all(a["objective_id"] < 6 for a in opening), (
        "retrieval is on earlier modules"
    )


def test_support_fades() -> None:  # Parsons, then fill in, then blank
    kinds = [
        ACTIVITIES[s["activity_id"]]["kind"]
        for s in MODULE["segments"]
        if s.get("activity_id") in ACTIVITIES
        and ACTIVITIES[s["activity_id"]]["kind"] in CODE_KINDS | {"parsons"}
    ]
    assert kinds == ["parsons", "complete_code", "write_code"]


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


def test_practice_targets_objective_6() -> None:
    practice = {
        a["objective_id"] for a in ACTIVITIES.values() if a["purpose"] != "retrieval"
    }
    assert practice == {6}


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
    options = {o["id"] for o in activity["config"]["options"]}
    assert activity["answer"]["correct"] in options
    assert options - {activity["answer"]["correct"]} <= set(activity["feedback"])


# --- code activities (NFR-M5) -----------------------------------------------


@pytest.mark.parametrize("activity_id", CODE_ACTIVITIES)
def test_reference_passes_every_test(activity_id: str) -> None:
    activity = ACTIVITIES[activity_id]
    provided = activity["config"]["provided_code"]
    tests = activity["config"]["example_tests"] + activity["answer"]["hidden_tests"]
    for test in tests:
        assert passes(provided, activity["answer"]["reference_solution"], test), test[
            "name"
        ]


@pytest.mark.parametrize("activity_id", CODE_ACTIVITIES)
def test_every_faulty_version_fails_a_hidden_test(activity_id: str) -> None:
    activity = ACTIVITIES[activity_id]
    provided = activity["config"]["provided_code"]
    answer = activity["answer"]
    assert answer["faulty_implementations"]
    for faulty in answer["faulty_implementations"]:
        results = [passes(provided, faulty["code"], t) for t in answer["hidden_tests"]]
        assert not all(results), f"{faulty['name']} passes every hidden test"


@pytest.mark.parametrize("activity_id", CODE_ACTIVITIES)
def test_starter_code_runs_but_is_not_solved(activity_id: str) -> None:
    activity = ACTIVITIES[activity_id]
    starter = activity["config"]["starter_code"]
    compile(starter, "<starter>", "exec")
    provided = activity["config"]["provided_code"]
    hidden = activity["answer"]["hidden_tests"]
    assert not all(passes(provided, starter, t) for t in hidden)


@pytest.mark.parametrize("activity_id", CODE_ACTIVITIES)
def test_every_hidden_test_has_feedback(activity_id: str) -> None:
    activity = ACTIVITIES[activity_id]
    names = [t["name"] for t in activity["answer"]["hidden_tests"]]
    assert len(names) == len(set(names))
    assert set(names) <= set(activity["feedback"])


def test_fill_in_only_removes_lines_from_the_reference() -> None:
    fill = ACTIVITIES["m4-fill"]
    reference = fill["answer"]["reference_solution"].splitlines()
    kept = [ln for ln in fill["config"]["starter_code"].splitlines() if "..." not in ln]
    assert all(line in reference for line in kept)
    assert fill["answer"]["reference_solution"] == WRITE["answer"]["reference_solution"]


# --- Parsons ----------------------------------------------------------------


def test_parsons_uses_every_line_once() -> None:
    ids = [line["id"] for line in PARSONS["config"]["lines"]]
    assert sorted(ids) == sorted(PARSONS["answer"]["order"])
    assert len(ids) == len(set(ids))
    grouped = [i for group in PARSONS["answer"]["groups"].values() for i in group]
    assert sorted(grouped) == sorted(ids)
    assert set(PARSONS["answer"]["groups"]) <= set(PARSONS["feedback"])


def test_every_accepted_parsons_order_is_a_working_bfs() -> None:
    orders = list(accepted_orders())
    assert len(orders) == 12  # 3! x 2!
    for order in orders:
        assert all_pass(parsons_code(order)), order


def test_parsons_starts_shuffled_and_wrong() -> None:
    shown = [line["id"] for line in PARSONS["config"]["lines"]]
    assert shown not in list(accepted_orders())
    assert not all_pass(parsons_code(shown))


def test_parsons_answer_is_the_reference() -> None:
    expected = WRITE["answer"]["reference_solution"]
    assert parsons_code(PARSONS["answer"]["order"]).split() == expected.split()


# --- graphs -----------------------------------------------------------------


@pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
def test_description_lists_every_vertex_and_edge(scenario_id: str) -> None:
    scenario = SCENARIOS[scenario_id]
    text = scenario["description"]
    assert text.startswith("Directed" if scenario["directed"] else "Undirected")
    arrow = " → " if scenario["directed"] else "–"
    for vertex in scenario["vertices"]:
        assert vertex["label"] in text
        if "name" in vertex:
            assert vertex["name"] in text
    for e in scenario["edges"]:
        assert f"{e['source']}{arrow}{e['target']}" in text
    assert f"{len(scenario['vertices'])} vertices" in text
    assert f"{len(scenario['edges'])} edges" in text


def test_every_scenario_is_used() -> None:
    used: set[str] = set()
    for activity in ACTIVITIES.values():
        if "scenario_id" in activity["config"]:
            used.add(activity["config"]["scenario_id"])
        tests = activity["config"].get("example_tests", []) + activity["answer"].get(
            "hidden_tests", []
        )
        used.update(t["scenario_id"] for t in tests)
    assert used == set(SCENARIOS)


def test_campus_order_matches_module_3() -> None:
    order = bfs_order(SCENARIOS["m4-campus"], "A")
    assert order == ["A", "C", "E", "B", "F", "D", "G"]
    path = SEED_DIR / "module_3" / "module.json"
    if path.exists():
        m3 = {a["id"]: a for a in _load(path)["activities"]}
        assert m3["m3-predict-campus"]["answer"]["expected_order"] == order


# --- answers ----------------------------------------------------------------


def test_recall_answers() -> None:
    campus = SCENARIOS["m4-campus"]
    assert correct_option("m4-recall-trace") == ", ".join(bfs_order(campus, "A"))
    neighbours = sorted(
        e["target"] if e["source"] == "C" else e["source"]
        for e in campus["edges"]
        if "C" in (e["source"], e["target"])
    )
    assert json.loads(correct_option("m4-recall-adjacency").strip("`")) == neighbours


def test_skip_check_and_closing() -> None:
    skip = SCENARIOS["m4-skip"]
    assert json.loads(correct_option("m4-skip-check").strip("`")) == bfs_order(
        skip, "W"
    )
    shuttle = SCENARIOS["m4-shuttle"]
    assert json.loads(correct_option("m4-closing").strip("`")) == bfs_order(
        shuttle, "D"
    )


def test_checkpoint_answers() -> None:
    assert correct_option("m4-ck-popleft") == "`v = queue.popleft()`"
    assert "twice" in correct_option("m4-ck-visited")
