"""Module 6 (Mastery check and report) content checks.

Checks issue #28: unseen items for all seven objectives in the amounts the ID document's
Table 1 asks for; each objective's success criterion as a rule, evaluated here on sample
results to show it matches Table 1; and review segments for each objective (FR-7.5).

It also runs the code items: reference solutions pass, faulty versions fail a hidden test
(NFR-M5), and the example tests for the write-tests items are valid and catch every faulty
version (FR-5.5). The code is our own fixture content, so it runs in-process with a time
limit. Student code never runs here; it goes through the code runner.
"""

import json
import math
import signal
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

SEED_DIR = Path(__file__).resolve().parents[1] / "app" / "seed"
MODULE_DIR = SEED_DIR / "module_6"


def _load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


MODULE = _load(MODULE_DIR / "module.json")
OBJECTIVES: dict[int, dict[str, Any]] = {
    o["id"]: o for o in _load(MODULE_DIR / "objectives.json")["objectives"]
}
SCENARIOS: dict[str, dict[str, Any]] = {
    s["id"]: s for s in _load(MODULE_DIR / "scenarios.json")["scenarios"]
}
ACTIVITIES: dict[str, dict[str, Any]] = {a["id"]: a for a in MODULE["activities"]}
REVIEW_SEGMENTS: dict[str, dict[str, Any]] = {
    s["id"]: s for s in MODULE["review_segments"]
}
FEEDBACK_PARTS = {"result", "reason", "next_step"}
CODE_KINDS = {"write_code", "fix_code"}
ITEM_SETS = [(obj, name) for obj in range(1, 8) for name in ("mastery", "retake")]


def items(obj: int, item_set: str) -> list[dict[str, Any]]:
    return [ACTIVITIES[i] for i in OBJECTIVES[obj]["item_sets"][item_set]]


# --- a reference evaluator for the rules (what the mastery service must do) ---


def parts(activity: dict[str, Any]) -> int:
    if activity["kind"] == "label_graph":
        return len(activity["config"]["markers"])
    if activity["kind"] == "classify_graphs":
        return len(activity["config"]["scenario_ids"])
    return 1


def evaluate(
    rule: dict[str, Any],
    acts: list[dict[str, Any]],
    attempts: dict[str, dict[str, Any]],
) -> str:
    """Return met_independently, met_with_support or not_yet (FR-7.2)."""
    results = [attempts[a["id"]] for a in acts]
    kind = rule["type"]
    if kind == "at_least_correct":
        assert rule["out_of"] == len(acts)
        met = sum(r["correct"] for r in results) >= rule["count"]
    elif kind == "at_least_fraction_of_parts":
        total = sum(parts(a) for a in acts)
        right = sum(attempts[a["id"]]["score"] * parts(a) for a in acts)
        met = right >= math.ceil(rule["fraction"] * total - 1e-9)
    elif kind == "at_most_errors":
        met = sum(r["errors"] for r in results) <= rule["errors"]
    elif kind == "all_correct":
        met = all(r["correct"] for r in results)
    else:
        raise AssertionError(f"unknown rule {kind}")
    if not met:
        return "not_yet"
    supported = any(r.get("hint", 0) >= 3 for r in results)
    return "met_with_support" if supported else "met_independently"


def attempt(correct: bool = True, **extra: Any) -> dict[str, Any]:
    return {"correct": correct, "score": 1.0 if correct else 0.0, "errors": 0, **extra}


@pytest.mark.parametrize(("obj", "item_set"), ITEM_SETS)
def test_rules_match_table_1(obj: int, item_set: str) -> None:
    rule, acts = OBJECTIVES[obj]["rule"], items(obj, item_set)
    all_right = {a["id"]: attempt() for a in acts}
    assert evaluate(rule, acts, all_right) == "met_independently"
    with_hint = {**all_right, acts[0]["id"]: attempt(hint=3)}
    assert evaluate(rule, acts, with_hint) == "met_with_support"
    all_wrong = {a["id"]: attempt(False, errors=99) for a in acts}
    assert evaluate(rule, acts, all_wrong) == "not_yet"


@pytest.mark.parametrize("item_set", ["mastery", "retake"])
def test_objective_1_needs_4_of_5(item_set: str) -> None:
    acts = items(1, item_set)
    assert len(acts) == 5
    four = {a["id"]: attempt(i > 0) for i, a in enumerate(acts)}
    three = {a["id"]: attempt(i > 1) for i, a in enumerate(acts)}
    assert evaluate(OBJECTIVES[1]["rule"], acts, four) != "not_yet"
    assert evaluate(OBJECTIVES[1]["rule"], acts, three) == "not_yet"


@pytest.mark.parametrize("item_set", ["mastery", "retake"])
def test_objective_2_needs_80_percent_of_parts(item_set: str) -> None:
    acts = items(2, item_set)
    kinds = sorted(a["kind"] for a in acts)
    assert kinds == ["classify_graphs"] + ["label_graph"] * 3  # 3 diagrams, 4 graphs
    assert next(parts(a) for a in acts if a["kind"] == "classify_graphs") == 4
    total = sum(parts(a) for a in acts)
    need = math.ceil(0.8 * total)

    def with_wrong(wrong: int) -> dict[str, dict[str, Any]]:
        result, left = {}, wrong
        for a in acts:
            miss = min(left, parts(a))
            left -= miss
            result[a["id"]] = {
                "correct": miss == 0,
                "score": 1 - miss / parts(a),
                "errors": miss,
            }
        return result

    rule = OBJECTIVES[2]["rule"]
    assert evaluate(rule, acts, with_wrong(total - need)) != "not_yet"
    assert evaluate(rule, acts, with_wrong(total - need + 1)) == "not_yet"


@pytest.mark.parametrize(
    ("obj", "item_set"), [(o, s) for o in (3, 4) for s in ("mastery", "retake")]
)
def test_objectives_3_and_4_need_3_of_4(obj: int, item_set: str) -> None:
    acts = items(obj, item_set)
    assert len(acts) == 4
    three = {a["id"]: attempt(i > 0) for i, a in enumerate(acts)}
    two = {a["id"]: attempt(i > 1) for i, a in enumerate(acts)}
    assert evaluate(OBJECTIVES[obj]["rule"], acts, three) != "not_yet"
    assert evaluate(OBJECTIVES[obj]["rule"], acts, two) == "not_yet"


@pytest.mark.parametrize("item_set", ["mastery", "retake"])
def test_objective_5_allows_one_error(item_set: str) -> None:
    acts = items(5, item_set)
    assert [a["kind"] for a in acts] == ["trace_table"]
    rule = OBJECTIVES[5]["rule"]
    one = {acts[0]["id"]: attempt(False, errors=1)}
    two = {acts[0]["id"]: attempt(False, errors=2)}
    assert evaluate(rule, acts, one) != "not_yet"
    assert evaluate(rule, acts, two) == "not_yet"


@pytest.mark.parametrize("item_set", ["mastery", "retake"])
def test_objectives_6_and_7_items(item_set: str) -> None:
    assert [a["kind"] for a in items(6, item_set)] == ["write_code"]
    kinds = [a["kind"] for a in items(7, item_set)]
    assert kinds == ["fix_code", "fix_code", "write_tests"]  # 2 bugs, 2 tests


# --- objectives, sets and review paths --------------------------------------


def test_objectives_cover_1_to_7() -> None:
    assert sorted(OBJECTIVES) == list(range(1, 8))
    assert MODULE["module"]["objectives"] == list(range(1, 8))
    assert len(MODULE["module"]["goals"]) == 7  # FR-2.3
    for obj in OBJECTIVES.values():
        assert obj["criterion"] and obj["text"] and obj["bloom_level"]
        assert set(obj["report_text"]) == {
            "met_independently",
            "met_with_support",
            "not_yet",
        }


@pytest.mark.parametrize(("obj", "item_set"), ITEM_SETS)
def test_items_are_tagged_and_mastery(obj: int, item_set: str) -> None:
    for activity in items(obj, item_set):
        assert activity["objective_id"] == obj
        assert activity["purpose"] == "mastery"


def test_sets_do_not_overlap_and_check_is_in_the_module() -> None:
    check, retake = set(), set()
    for obj in OBJECTIVES.values():
        check.update(obj["item_sets"]["mastery"])
        retake.update(obj["item_sets"]["retake"])
    assert not check & retake
    in_flow = {s["activity_id"] for s in MODULE["segments"] if "activity_id" in s}
    assert in_flow == check
    non_code = [
        i
        for i in check | retake
        if ACTIVITIES[i]["kind"] not in CODE_KINDS | {"write_tests"}
    ]
    prompts = [ACTIVITIES[i]["prompt"] for i in non_code]
    assert len(prompts) == len(set(prompts)), "retake items are new questions"


def test_items_are_unseen_in_earlier_modules() -> None:
    mine = {
        ACTIVITIES[i]["prompt"]
        for o in OBJECTIVES.values()
        for i in o["item_sets"]["mastery"]
    }
    graphs = {
        frozenset((e["source"], e["target"]) for e in s["edges"])
        for s in SCENARIOS.values()
    }
    for n in range(1, 6):
        path = SEED_DIR / f"module_{n}"
        if not path.exists():
            continue
        earlier = _load(path / "module.json")["activities"]
        assert not mine & {a["prompt"] for a in earlier}
        for s in _load(path / "scenarios.json")["scenarios"]:
            if len(s["vertices"]) >= 6:
                assert (
                    frozenset((e["source"], e["target"]) for e in s["edges"])
                    not in graphs
                )


@pytest.mark.parametrize("obj", range(1, 8))
def test_review_path(obj: int) -> None:  # FR-7.5
    path = OBJECTIVES[obj]["review_path"]
    assert path["then"] == "retake"
    segments = [REVIEW_SEGMENTS[s] for s in path["segments"]]
    assert all(s["review_for_objective"] == obj for s in segments)
    assert [s["kind"] for s in segments] == ["text", "activity"]
    review = ACTIVITIES[segments[1]["activity_id"]]
    assert review["purpose"] == "review" and review["objective_id"] == obj
    for activity_id in segments[0]["revisit_activity_ids"]:
        module = int(activity_id[1])
        path_m = SEED_DIR / f"module_{module}" / "module.json"
        if path_m.exists():
            assert activity_id in {a["id"] for a in _load(path_m)["activities"]}


def test_every_activity_is_used() -> None:
    used = {i for o in OBJECTIVES.values() for s in o["item_sets"].values() for i in s}
    used |= {s["activity_id"] for s in MODULE["review_segments"] if "activity_id" in s}
    assert used == set(ACTIVITIES)


# --- hints and feedback -----------------------------------------------------


@pytest.mark.parametrize("activity_id", sorted(ACTIVITIES))
def test_activity_has_four_hints(activity_id: str) -> None:
    hints = ACTIVITIES[activity_id]["hints"]
    assert len(hints) == 4
    assert hints[3].startswith("Answer:")


@pytest.mark.parametrize("activity_id", sorted(ACTIVITIES))
def test_feedback_has_three_parts(activity_id: str) -> None:
    feedback = ACTIVITIES[activity_id]["feedback"]
    assert "correct" in feedback
    for key, message in feedback.items():
        assert set(message) == FEEDBACK_PARTS, f"{key} needs result, reason, next_step"
        assert all(message[part].strip() for part in FEEDBACK_PARTS)


@pytest.mark.parametrize("activity_id", sorted(ACTIVITIES))
def test_choice_answers(activity_id: str) -> None:
    activity = ACTIVITIES[activity_id]
    if activity["kind"] == "multiple_choice":
        options = {o["id"] for o in activity["config"]["options"]}
        assert activity["answer"]["correct"] in options
        assert options - {activity["answer"]["correct"]} <= set(activity["feedback"])
    elif activity["kind"] == "matching":
        left = {i["id"] for i in activity["config"]["left"]}
        assert set(activity["answer"]["pairs"]) == left <= set(activity["feedback"])
        assert set(activity["answer"]["pairs"].values()) <= {
            i["id"] for i in activity["config"]["right"]
        }
    else:
        pytest.skip("not a choice item")


# --- graph items ------------------------------------------------------------


def bfs_rows(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    adj: dict[str, list[str]] = {v["id"]: [] for v in scenario["vertices"]}
    for e in scenario["edges"]:
        adj[e["source"]].append(e["target"])
        if not scenario["directed"]:
            adj[e["target"]].append(e["source"])
    start = scenario["start_vertex"]
    visited, queue, rows = {start}, deque([start]), []
    while queue:
        vertex = queue.popleft()
        for n in sorted(adj[vertex]):
            if n not in visited:
                visited.add(n)
                queue.append(n)
        rows.append(
            {"current": vertex, "queue": list(queue), "visited": sorted(visited)}
        )
    return rows


@pytest.mark.parametrize("activity_id", sorted(ACTIVITIES))
def test_graph_item_answers(activity_id: str) -> None:
    activity = ACTIVITIES[activity_id]
    config = activity["config"]
    if activity["kind"] == "trace_table":
        scenario = SCENARIOS[config["scenario_id"]]
        assert 6 <= len(scenario["vertices"]) <= 8  # Table 1: 6 to 8 vertices
        assert activity["answer"]["rows"] == bfs_rows(scenario)
        assert config["columns"] == ["current", "queue", "visited"]
    elif activity["kind"] == "label_graph":
        graph = SCENARIOS[config["scenario_id"]]
        arrow = " → " if graph["directed"] else "–"
        edges = {(e["source"], e["target"]) for e in graph["edges"]}
        for marker in config["markers"]:
            target = marker["target"]
            if target["type"] == "vertex":
                expected = f"Vertex {target['id']}"
            else:
                assert (target["source"], target["target"]) in edges
                expected = f"Edge {target['source']}{arrow}{target['target']}"
            assert activity["answer"]["labels"][str(marker["marker"])] == expected
            assert expected in config["label_options"]
    elif activity["kind"] == "classify_graphs":
        for sid, label in activity["answer"]["classes"].items():
            assert label == ("directed" if SCENARIOS[sid]["directed"] else "undirected")
        assert set(activity["answer"]["classes"].values()) == {"directed", "undirected"}
    else:
        pytest.skip("not a graph item")


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


def test_every_scenario_is_used() -> None:
    used: set[str] = set()
    for activity in ACTIVITIES.values():
        config = activity["config"]
        if "scenario_id" in config:
            used.add(config["scenario_id"])
        used.update(config.get("scenario_ids", []))
        tests = config.get("example_tests", []) + activity["answer"].get(
            "hidden_tests", []
        )
        used.update(t["scenario_id"] for t in tests)
    assert used == set(SCENARIOS)


# --- code items -------------------------------------------------------------


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


def passes(code: str, test_code: str, name: str = "test") -> bool:
    namespace: dict[str, Any] = {}
    try:
        with time_limit(2):
            exec(compile(code, "<solution>", "exec"), namespace)  # noqa: S102
            exec(compile(test_code, f"<{name}>", "exec"), namespace)  # noqa: S102
    except Exception:  # noqa: BLE001
        return False
    return True


CODE_ITEMS = sorted(a["id"] for a in ACTIVITIES.values() if a["kind"] in CODE_KINDS)
TEST_ITEMS = sorted(a["id"] for a in ACTIVITIES.values() if a["kind"] == "write_tests")


@pytest.mark.parametrize("activity_id", CODE_ITEMS)
def test_code_item(activity_id: str) -> None:
    activity = ACTIVITIES[activity_id]
    provided = activity["config"]["provided_code"] + "\n"
    answer = activity["answer"]
    hidden = answer["hidden_tests"]
    every = activity["config"]["example_tests"] + hidden
    for test in every:
        assert passes(
            provided + answer["reference_solution"], test["code"], test["name"]
        )
    for faulty in answer["faulty_implementations"]:
        results = [passes(provided + faulty["code"], t["code"]) for t in hidden]
        assert not all(results), f"{faulty['name']} passes every hidden test"
    starter = activity["config"]["starter_code"]
    assert not all(passes(provided + starter, t["code"]) for t in hidden)
    names = [t["name"] for t in hidden]
    assert len(names) == len(set(names)) and set(names) <= set(activity["feedback"])
    if activity["kind"] == "fix_code":
        assert starter in [f["code"] for f in answer["faulty_implementations"]]


@pytest.mark.parametrize("activity_id", TEST_ITEMS)
def test_write_tests_item(activity_id: str) -> None:  # FR-5.5
    activity = ACTIVITIES[activity_id]
    provided = activity["config"]["provided_code"] + "\n"
    answer = activity["answer"]
    required = activity["config"]["required_tests"]
    assert required == ["test_cycle", "test_disconnected"]
    for name in required:
        assert f"def {name}(" in activity["config"]["starter_code"]
    example = answer["example_solution"]
    reference = provided + answer["reference_implementation"] + "\n" + example
    for name in required:
        assert passes(reference, f"{name}()", name), f"{name} fails on a correct BFS"
    for faulty in answer["faulty_implementations"]:
        code = provided + faulty["code"] + "\n" + example
        assert not all(passes(code, f"{n}()", n) for n in required), faulty["name"]
