"""Matching (FR-4.1, objectives 1 and 3), fix the bug and choose tests (FR-5.5, objective 7): the
checkers, the content checks the seed runs (app/services/content.py), and the attempts endpoint
end to end, without ever sending the solution to the browser."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from support import open_module

from app.models import Activity
from app.seed import load, read_fixtures
from app.services.checking import (
    BUG_LEFT_IN,
    EXTRA_LINE,
    FIX_NOT_NEEDED,
    MISSED_TEST,
    NO_MATCH,
    NOT_EXPOSING,
    OUT_OF_PLACE,
    UNKNOWN_TEST,
    WRONG_FIX,
    WRONG_MATCH,
    check_activity,
    is_blank,
)
from app.services.content import validate_activity

STUDENT = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}

# --- Content: one realistic activity of each kind --------------------------------------------

MATCHING_CONFIG: dict[str, Any] = {
    "prompt": "Match each term with its meaning.",
    "left": [
        {"id": "vertex", "label": "Vertex"},
        {"id": "edge", "label": "Edge"},
        {"id": "directed", "label": "Directed graph"},
    ],
    "right": [
        {"id": "point", "label": "A point in the graph"},
        {"id": "link", "label": "A connection between two points"},
        {"id": "oneway", "label": "Every connection goes one way"},
        {"id": "weight", "label": "A cost on a connection"},  # a distractor
    ],
}
MATCHING_SOLUTION: dict[str, Any] = {
    "pairs": {"vertex": "point", "edge": "link", "directed": "oneway"},
    "feedback": {"edge": "An edge connects two vertices; a weight is a cost some edges carry."},
}

# A BFS that pops from the wrong end of the queue (a stack: that's DFS), and marks a vertex
# visited only when it is dequeued, so a vertex can be queued twice.
FIX_CONFIG: dict[str, Any] = {
    "prompt": "This BFS has two bugs. Fix them.",
    "lines": [
        {"id": 1, "text": "def bfs(graph, start):"},
        {"id": 2, "text": "    queue, visited, order = deque([start]), set(), []"},
        {"id": 3, "text": "    while queue:"},
        {"id": 4, "text": "        v = queue.pop()"},
        {"id": 5, "text": "        visited.add(v)"},
        {"id": 6, "text": "        order.append(v)"},
        {"id": 7, "text": "        for n in sorted(graph[v]):"},
        {"id": 8, "text": "            if n not in visited:"},
        {"id": 9, "text": "                queue.append(n)"},
        {"id": 10, "text": "    return order"},
    ],
    "corrections": [
        {"id": 20, "text": "    queue, visited, order = deque([start]), {start}, []"},
        {"id": 21, "text": "        v = queue.popleft()"},
        {"id": 22, "text": "                visited.add(n)"},
        {"id": 23, "text": "        v = queue[0]"},  # a distractor
    ],
}
FIX_SOLUTION: dict[str, Any] = {
    # Start visited, take from the front, mark a neighbour visited as it is queued.
    "order": [1, 20, 3, 21, 6, 7, 8, 22, 9, 10],
    "feedback": {
        4: "pop() takes the newest vertex, as a stack does: BFS takes the oldest.",
        5: "Marking a vertex when it leaves the queue lets it be queued twice.",
    },
}
FIX_RIGHT = FIX_SOLUTION["order"]

# Test cases for a BFS that forgets the visited set: it loops on a cycle and repeats vertices.
CYCLE = {
    "id": "cycle",
    "vertices": ["A", "B", "C"],
    "edges": [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "C"},
        {"source": "C", "target": "A"},
    ],
    "start_vertex": "A",
    "expected": ["A", "B", "C"],
}
PATH = {
    "id": "path",
    "vertices": ["A", "B"],
    "edges": [{"source": "A", "target": "B"}],
    "start_vertex": "A",
    "expected": ["A", "B"],
}
DIAMOND = {
    "id": "diamond",
    "vertices": ["A", "B", "C", "D"],
    "edges": [
        {"source": "A", "target": "B"},
        {"source": "A", "target": "C"},
        {"source": "B", "target": "D"},
        {"source": "C", "target": "D"},
    ],
    "start_vertex": "A",
    "expected": ["A", "B", "C", "D"],
}
TRACE_CONFIG: dict[str, Any] = {
    "directed": False,
    "vertices": ["A", "B", "D"],
    "edges": [{"source": "A", "target": "B"}, {"source": "B", "target": "D"}],
    "start_vertex": "B",
}
TESTS_CONFIG: dict[str, Any] = {
    "prompt": "Select every test case this BFS fails.",
    "code": "def bfs(graph, start): ...",
    "tests": [CYCLE, PATH, DIAMOND],
}
TESTS_SOLUTION: dict[str, Any] = {
    "exposing": ["cycle", "diamond"],
    "feedback": {"path": "No vertex is reachable twice here, so the missing check never matters."},
}


def grade(kind: str, config: dict[str, Any], solution: dict[str, Any], **submitted: Any) -> Any:
    return check_activity(kind, config, solution, submitted)


# --- Matching --------------------------------------------------------------------------------


def test_matching_all_right() -> None:
    result = grade("matching", MATCHING_CONFIG, MATCHING_SOLUTION, pairs=MATCHING_SOLUTION["pairs"])
    assert (result.correct, result.score, result.feedback) == (True, 1.0, "All correct.")


def test_a_right_answer_gets_the_content_s_explanation() -> None:
    """A right answer says why it is right when the content explains it (FR-4.2); a wrong one
    keeps its own feedback."""
    solution = {**MATCHING_SOLUTION, "explanation": "Each vertex pairs with its own neighbours."}
    right = grade("matching", MATCHING_CONFIG, solution, pairs=MATCHING_SOLUTION["pairs"])
    assert (right.correct, right.feedback) == (True, "Each vertex pairs with its own neighbours.")
    wrong = grade("matching", MATCHING_CONFIG, solution, pairs={})
    assert not wrong.correct
    assert wrong.feedback != solution["explanation"]


def test_an_empty_explanation_is_refused() -> None:
    with pytest.raises(ValueError, match="explanation"):
        validate_activity("matching", MATCHING_CONFIG, {**MATCHING_SOLUTION, "explanation": ""})


def test_matching_marks_each_pair_with_the_reason() -> None:
    result = grade(
        "matching",
        MATCHING_CONFIG,
        MATCHING_SOLUTION,
        pairs={"vertex": "point", "edge": "weight", "directed": "link"},
    )
    assert not result.correct
    assert result.score == pytest.approx(1 / 3)
    assert [(p.ref, p.correct, p.message) for p in result.parts] == [
        (0, True, None),
        (1, False, MATCHING_SOLUTION["feedback"]["edge"]),
        (2, False, WRONG_MATCH),
    ]


def test_matching_an_unmatched_item_fails() -> None:
    result = grade("matching", MATCHING_CONFIG, MATCHING_SOLUTION, pairs={"vertex": "point"})
    assert [p.message for p in result.parts] == [None, NO_MATCH, NO_MATCH]


# --- Fix the bug -----------------------------------------------------------------------------


def test_fix_the_bug_the_fixed_program_passes() -> None:
    result = grade("fix_the_bug", FIX_CONFIG, FIX_SOLUTION, order=FIX_RIGHT)
    assert result.correct
    assert result.score == 1.0


def test_fix_the_bug_says_what_is_wrong_at_each_position() -> None:
    order = [
        1,
        2,  # the faulty line left in: its content message
        3,
        23,  # the wrong correction
        6,
        7,
        8,
        22,
        9,
        10,
    ]
    parts = grade("fix_the_bug", FIX_CONFIG, FIX_SOLUTION, order=order).parts
    assert parts[1].message == BUG_LEFT_IN  # line 2 has no content message: the default
    assert parts[3].message == WRONG_FIX
    assert sum(p.correct for p in parts) == 8


def test_fix_the_bug_a_buggy_line_left_in_gets_its_reason() -> None:
    order = [1, 20, 3, 4, 6, 7, 8, 22, 9, 10]
    parts = grade("fix_the_bug", FIX_CONFIG, FIX_SOLUTION, order=order).parts
    assert parts[3].message == FIX_SOLUTION["feedback"][4]


def test_fix_the_bug_a_needless_correction_and_a_moved_line() -> None:
    order = [1, 20, 3, 21, 23, 7, 8, 22, 9, 10]  # position 4 should be line 6, left as it was
    parts = grade("fix_the_bug", FIX_CONFIG, FIX_SOLUTION, order=order).parts
    assert parts[4].message == FIX_NOT_NEEDED
    # Two lines swapped: moving either one fixes it, so one of them is marked (#145).
    moved = [1, 20, 3, 21, 7, 6, 8, 22, 9, 10]
    wrong = [
        p
        for p in grade("fix_the_bug", FIX_CONFIG, FIX_SOLUTION, order=moved).parts
        if not p.correct
    ]
    assert [p.ref for p in wrong] in ([4], [5])
    assert wrong[0].message == OUT_OF_PLACE


def test_fix_the_bug_a_short_or_long_answer_fails_the_positions_it_affects() -> None:
    short = grade("fix_the_bug", FIX_CONFIG, FIX_SOLUTION, order=FIX_RIGHT[:-1]).parts
    assert short[-1].message == "A line is missing from this position."
    long = grade("fix_the_bug", FIX_CONFIG, FIX_SOLUTION, order=[*FIX_RIGHT, 23]).parts
    assert long[-1].message == "This line does not belong in the answer."


def test_fix_the_bug_a_made_up_id_is_an_extra_line_not_a_bug_left_in() -> None:
    order = [1, 20, 3, 21, 6, 7, 8, 22, 9, 99]  # 99 is neither a line nor a correction
    parts = grade("fix_the_bug", FIX_CONFIG, FIX_SOLUTION, order=order).parts
    assert parts[-1].message == EXTRA_LINE


# --- Choose tests ----------------------------------------------------------------------------


def test_choose_tests_exactly_the_exposing_ones_pass() -> None:
    result = grade("choose_tests", TESTS_CONFIG, TESTS_SOLUTION, selected=["diamond", "cycle"])
    assert result.correct


@pytest.mark.parametrize("selected", [[], ["cycle", "path", "diamond"]])
def test_choose_tests_none_or_all_cannot_pass(selected: list[str]) -> None:
    assert not grade("choose_tests", TESTS_CONFIG, TESTS_SOLUTION, selected=selected).correct


def test_choose_tests_messages() -> None:
    parts = grade("choose_tests", TESTS_CONFIG, TESTS_SOLUTION, selected=["path"]).parts
    assert [(p.correct, p.message) for p in parts] == [
        (False, MISSED_TEST),
        (False, TESTS_SOLUTION["feedback"]["path"]),
        (False, MISSED_TEST),
    ]
    parts = grade("choose_tests", TESTS_CONFIG, {"exposing": ["cycle"]}, selected=["path"]).parts
    assert parts[1].message == NOT_EXPOSING


def test_choose_tests_a_made_up_test_id_cannot_pad_a_right_answer() -> None:
    result = grade(
        "choose_tests", TESTS_CONFIG, TESTS_SOLUTION, selected=["cycle", "diamond", "junk"]
    )
    assert not result.correct
    assert [p.correct for p in result.parts] == [True, True, True, False]
    assert (result.parts[-1].ref, result.parts[-1].message) == (3, UNKNOWN_TEST)


# --- Content checks (run by the seed and in CI) ----------------------------------------------


FILL_CONFIG: dict[str, Any] = {
    "code": "if v __1__ self.adjacency:\n    self.adjacency[v] = __2__",
    "blanks": [1, 2],
    "options": ["in", "not in", "[]", "None"],
}
FILL_SOLUTION: dict[str, Any] = {
    "answers": {"1": "not in", "2": "[]"},
    "feedback": {"1": {"in": "With in, a new vertex never gets a list."}},
}


# A Parsons problem with a group (2 and 3 in either order), an alternative that moves 1 to the end,
# and a distractor (20).
PARSONS_CONFIG: dict[str, Any] = {
    "lines": [{"id": i, "text": f"line {i}"} for i in (1, 2, 3, 20)],
}
PARSONS_SOLUTION: dict[str, Any] = {"order": [1, [2, 3]], "alternatives": [[[2, 3], 1]]}


def test_the_examples_are_valid_content() -> None:
    validate_activity("matching", MATCHING_CONFIG, MATCHING_SOLUTION)
    validate_activity("fix_the_bug", FIX_CONFIG, FIX_SOLUTION)
    validate_activity("choose_tests", TESTS_CONFIG, TESTS_SOLUTION)
    validate_activity("fill_in", FILL_CONFIG, FILL_SOLUTION)
    validate_activity("fill_in", FILL_CONFIG, {"answers": FILL_SOLUTION["answers"]})  # no feedback
    validate_activity("parsons", {"lines": [{"id": 1, "text": "x"}]}, {"order": [1]})
    validate_activity("parsons", PARSONS_CONFIG, PARSONS_SOLUTION)  # groups and an alternative


@pytest.mark.parametrize(
    ("kind", "config", "solution", "problem"),
    [
        ("matching", MATCHING_CONFIG, {"pairs": {"vertex": "point"}}, "every left item"),
        (
            "matching",
            MATCHING_CONFIG,
            {"pairs": {**MATCHING_SOLUTION["pairs"], "edge": "nope"}},
            "unknown right items",
        ),
        (
            "matching",
            {**MATCHING_CONFIG, "left": [*MATCHING_CONFIG["left"], {"id": "edge", "label": "x"}]},
            MATCHING_SOLUTION,
            "share an id",
        ),
        (
            "matching",
            MATCHING_CONFIG,
            {**MATCHING_SOLUTION, "feedback": {"nope": "x"}},
            "unknown left items",
        ),
        ("fix_the_bug", FIX_CONFIG, {"order": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]}, "nothing to fix"),
        ("fix_the_bug", FIX_CONFIG, {**FIX_SOLUTION, "feedback": {20: "x"}}, "not faulty-program"),
        (
            "choose_tests",
            TESTS_CONFIG,
            {**TESTS_SOLUTION, "feedback": {"nope": "x"}},
            "unknown test cases",
        ),
        (
            "multiple_choice",
            {"prompt": "?", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]},
            {"correct": "a", "feedback": {"z": "x"}},
            "unknown options",
        ),
        ("fill_in", FILL_CONFIG, {"answers": {"1": "not in"}}, r"no answer for blanks \[2\]"),
        (
            "fill_in",
            FILL_CONFIG,
            {"answers": {**FILL_SOLUTION["answers"], "3": "in"}},
            "blanks that don't exist",
        ),
        ("fill_in", FILL_CONFIG, {"answers": {"1": "not in", "2": "{}"}}, "not one of the options"),
        (
            "fill_in",
            FILL_CONFIG,
            {**FILL_SOLUTION, "feedback": {"9": {"in": "x"}}},
            "blank 9, which doesn't exist",
        ),
        (
            "fill_in",
            FILL_CONFIG,
            {**FILL_SOLUTION, "feedback": {"1": {"is": "x"}}},
            "tokens that aren't options",
        ),
        (
            "fill_in",
            FILL_CONFIG,
            {**FILL_SOLUTION, "feedback": {"2": {"[]": "x"}}},
            "the correct token",
        ),
        ("essay", {}, {}, "unknown activity kind"),
        ("parsons", PARSONS_CONFIG, {"order": [1, 2, 99]}, "the order uses unknown line ids .99."),
        ("parsons", PARSONS_CONFIG, {"order": [1, [2, 3], 3]}, "the order uses a line twice"),
        ("parsons", PARSONS_CONFIG, {"order": [1, [2, 3], []]}, "at least two ids, not .]"),
        ("parsons", PARSONS_CONFIG, {"order": [1, [2], 3]}, "at least two ids, not .2."),
        ("parsons", PARSONS_CONFIG, {"order": [1, [2, "x"]]}, "'x' in the group .2, 'x'. is not"),
        ("parsons", PARSONS_CONFIG, {"order": [1, [[2, 3]]]}, "not another group"),
        (
            "parsons",
            PARSONS_CONFIG,
            {"order": [1, [2, 3]], "alternatives": [[1, [2, 3]]]},
            "alternative 1 is the order itself",
        ),
        ("parsons", PARSONS_CONFIG, {"order": 5}, "order must be a list of line ids"),
        ("parsons", PARSONS_CONFIG, {"order": [1, True, 3]}, "True is not a line id"),
        ("parsons", PARSONS_CONFIG, {"order": [1, "2", 3]}, "'2' is not a line id"),
        (
            "parsons",
            PARSONS_CONFIG,
            {"order": [1, 2, 3], "alternatives": [[1, 2.5]]},
            "alternative 1: 2.5",
        ),
        (
            "parsons",
            PARSONS_CONFIG,
            {"order": [1, 2, 3], "alternatives": {"a": 1}},
            "list of orders",
        ),
        ("parsons", PARSONS_CONFIG, {"order": []}, "at least 1 item"),
        ("parsons", PARSONS_CONFIG, {"order": [1, 2], "also": [[2, 1]]}, "Extra inputs"),
        (
            "parsons",
            {"lines": [*PARSONS_CONFIG["lines"], {"id": 1, "text": "again"}]},
            {"order": [1, 2, 3]},
            "two lines share an id",
        ),
        (
            "parsons",
            PARSONS_CONFIG,
            {"order": [1, 2, 3], "alternatives": [[1, 3]]},
            "alternative 1 must use the same lines",
        ),
        (
            "parsons",
            PARSONS_CONFIG,
            {"order": [1, 2, 3], "alternatives": [[1, 3, 9]]},
            "alternative 1 uses unknown line ids .9.",
        ),
        (
            "parsons",
            PARSONS_CONFIG,
            {"order": [1, 2, 3], "alternatives": [[1, 3, 2], [1, 3, 2, 3]]},
            "alternative 2 uses a line twice",
        ),
        (
            "parsons",
            PARSONS_CONFIG,
            {"order": [1, [2, 3]], "alternatives": [[1, [3, 2]]]},
            "alternative 1 accepts nothing that the order doesn't already",
        ),
        (
            "parsons",
            PARSONS_CONFIG,
            {"order": [1, [2, 3]], "alternatives": [[1, 3, 2]]},  # an expansion of the order
            "alternative 1 accepts nothing that the order",
        ),
        (
            "parsons",
            PARSONS_CONFIG,
            {"order": [1, 2, 3], "alternatives": [[[2, 3], 1], [3, 2, 1]]},
            "alternative 2 accepts nothing that alternative 1",
        ),
        ("fix_the_bug", FIX_CONFIG, {"order": [[1, 2], 3, 4, 5, 6, 7, 8, 9, 10]}, "nothing to fix"),
        (
            "fix_the_bug",
            FIX_CONFIG,
            {**FIX_SOLUTION, "alternatives": [[1, 20, 3, 21, 6, 7, 8, 22]]},
            "alternative 1 must use the same lines",
        ),
        (
            "parsons",
            PARSONS_CONFIG,
            {"order": [1, 2, 3], "alternatives": [[1, 2, 3, 20]]},
            "the same lines as the order",
        ),
        (
            "parsons",
            PARSONS_CONFIG,
            {"order": [1, 2, 3], "alternatives": [[1, 2, 3]] * 21},
            "at most 20 items",
        ),
        ("fix_the_bug", FIX_CONFIG, {"order": [1, 99]}, "unknown line ids"),
        ("fix_the_bug", FIX_CONFIG, {"order": [1, 20, 20]}, "a line twice"),
        (
            "fix_the_bug",
            {**FIX_CONFIG, "corrections": [{"id": 4, "text": "x"}]},
            FIX_SOLUTION,
            "its own id",
        ),
        ("choose_tests", TESTS_CONFIG, {"exposing": ["cycle", "path", "diamond"]}, "all of them"),
        ("choose_tests", TESTS_CONFIG, {"exposing": ["nope"]}, "unknown test cases"),
        (
            "choose_tests",
            {**TESTS_CONFIG, "tests": [{**DIAMOND, "expected": ["A", "C", "B", "D"]}, PATH]},
            {"exposing": ["diamond"]},
            "but BFS visits",
        ),
        (
            "choose_tests",
            {**TESTS_CONFIG, "tests": [{**PATH, "start_vertex": "not a vertex!"}, CYCLE]},
            {"exposing": ["cycle"]},
            "start_vertex",
        ),
        (
            "choose_tests",
            {**TESTS_CONFIG, "tests": [{**PATH, "start_vertex": "Z"}, CYCLE]},
            {"exposing": ["cycle"]},
            "test case 'path'",
        ),
    ],
)
def test_content_that_cannot_work_is_refused(
    kind: str, config: dict[str, Any], solution: dict[str, Any], problem: str
) -> None:
    with pytest.raises(ValueError, match=problem):
        validate_activity(kind, config, solution)


def test_the_seed_loads_the_new_kinds_and_refuses_a_broken_one(tmp_path: Path, db: Session) -> None:
    activities = [
        {"id": 1, "kind": "matching", "title": "Terms", "config": MATCHING_CONFIG,
         "solution": MATCHING_SOLUTION},
        {"id": 2, "kind": "fix_the_bug", "title": "Fix it", "config": FIX_CONFIG,
         "solution": json.loads(json.dumps(FIX_SOLUTION))},
        {"id": 3, "kind": "choose_tests", "title": "Tests", "config": TESTS_CONFIG,
         "solution": TESTS_SOLUTION},
    ]  # fmt: skip
    (tmp_path / "content.json").write_text(json.dumps({"activities": activities}))
    load(db, tmp_path)
    assert {a.kind for a in db.query(Activity)} == {"matching", "fix_the_bug", "choose_tests"}

    broken = {**activities[2], "solution": {"exposing": ["cycle", "path", "diamond"]}}
    (tmp_path / "content.json").write_text(json.dumps({"activities": [broken]}))
    with pytest.raises(ValueError, match="activity 3: every test case exposes"):
        read_fixtures(tmp_path)


# --- End to end through the API ----------------------------------------------------------------


def make(db: Session, kind: str, config: dict[str, Any], solution: dict[str, Any]) -> int:
    activity = Activity(
        kind=kind,
        title=kind,
        visible=True,
        config=config,
        solution=solution,
        module_id=open_module(db),
    )
    db.add(activity)
    db.commit()
    return activity.id


@pytest.mark.parametrize(
    ("kind", "config", "solution", "right", "secret"),
    [
        ("matching", MATCHING_CONFIG, MATCHING_SOLUTION, {"pairs": MATCHING_SOLUTION["pairs"]},
         "a weight is a cost"),
        ("fix_the_bug", FIX_CONFIG, FIX_SOLUTION, {"order": FIX_RIGHT}, "as a stack does"),
        ("choose_tests", TESTS_CONFIG, TESTS_SOLUTION, {"selected": ["cycle", "diamond"]},
         "exposing"),
        ("fill_in", FILL_CONFIG, FILL_SOLUTION, {"answers": {"1": "not in", "2": "[]"}},
         "never gets a list"),
    ],
)  # fmt: skip
def test_each_kind_through_the_api(
    client: TestClient,
    db: Session,
    kind: str,
    config: dict[str, Any],
    solution: dict[str, Any],
    right: dict[str, Any],
    secret: str,
) -> None:
    activity_id = make(db, kind, config, solution)
    assert client.post("/api/auth/register", json=STUDENT).status_code == 201

    shown = client.get(f"/api/activities/{activity_id}")
    assert shown.status_code == 200
    assert shown.json()["kind"] == kind
    assert secret not in shown.text  # the solution and its feedback stay on the server

    url = f"/api/activities/{activity_id}/attempts"
    passed = client.post(url, json={"submitted": right})
    assert passed.status_code == 201
    assert passed.json()["correct"] is True
    # A submission in the wrong shape is refused, not crashed on.
    assert client.post(url, json={"submitted": {"nonsense": 1}}).status_code == 422


# --- Fix the bug: every correct order (FR-5.5, #145) ---------------------------------------------

# The fixed program's lines 3 and 6, and the correction 22 and line 9, may swap.
GROUPED_FIX: dict[str, Any] = {**FIX_SOLUTION, "order": [1, 20, [3, 21], 6, 7, 8, [22, 9], 10]}


def test_fix_the_bug_groups_accept_every_listed_order() -> None:
    validate_activity("fix_the_bug", FIX_CONFIG, GROUPED_FIX)
    for order in (
        [1, 20, 3, 21, 6, 7, 8, 22, 9, 10],
        [1, 20, 21, 3, 6, 7, 8, 9, 22, 10],
    ):
        result = grade("fix_the_bug", FIX_CONFIG, GROUPED_FIX, order=order)
        assert result.correct, order
        assert result.feedback == "All correct."


def test_fix_the_bug_marks_the_wrong_correction_against_its_own_place() -> None:
    # The swap inside the group is fine; the stack-style correction 23 in 21's place is not.
    result = grade("fix_the_bug", FIX_CONFIG, GROUPED_FIX, order=[1, 20, 23, 3, 6, 7, 8, 9, 22, 10])
    wrong = [p for p in result.parts if not p.correct]
    assert [(p.ref, p.message) for p in wrong] == [(2, WRONG_FIX)]


def test_fix_the_bug_a_bug_left_in_gets_the_contents_reason() -> None:
    result = grade("fix_the_bug", FIX_CONFIG, GROUPED_FIX, order=[1, 20, 3, 4, 6, 7, 8, 22, 9, 10])
    assert [p.message for p in result.parts if not p.correct] == [FIX_SOLUTION["feedback"][4]]


def test_fix_the_bug_a_removed_line_is_named_in_the_summary() -> None:
    result = grade("fix_the_bug", FIX_CONFIG, GROUPED_FIX, order=[1, 20, 3, 21, 6, 7, 8, 22, 10])
    assert not result.correct
    assert result.feedback == (
        "9 of 10 correct. 1 line is missing: put it back, or add its correction."
    )


def test_the_reviewers_objective_7_case_is_correct() -> None:
    # 621 with visited.add(n) and queue.append(n) swapped: was "11 of 13" (#145 review). 621 was a
    # new bug since #214 (C2) and is now 631 (#223 review), so the case is 631's fix with the same
    # two lines swapped.
    item = next(a for a in read_fixtures().activities if a.id == 631)
    result = check_activity(
        "fix_the_bug",
        item.config,
        item.solution,
        {"order": [1, 2, 3, 4, 5, 6, 7, 8, 21, 10, 12, 11, 13]},
    )
    assert result.correct


def test_a_solution_stored_with_string_ids_still_grades() -> None:
    """Strict ids are a content rule (validate_activity); grading parses a stored solution
    laxly, so a "3" stored by an older seed or an edit still grades (#145 review)."""
    config = {"lines": [{"id": i, "text": f"line {i}"} for i in (1, 2, 3)]}
    stored = {"order": [1, ["2", "3"]]}
    assert check_activity("parsons", config, stored, {"order": [1, 3, 2]}).correct
    assert not check_activity("parsons", config, stored, {"order": [3, 2, 1]}).correct
    fix = {**FIX_SOLUTION, "order": [str(i) for i in FIX_SOLUTION["order"]]}
    assert check_activity("fix_the_bug", FIX_CONFIG, fix, {"order": FIX_RIGHT}).correct
    with pytest.raises(ValueError, match="'2' in the group"):
        validate_activity("parsons", config, stored)


def test_no_mastery_item_explains_its_answer_yet() -> None:
    """The mastery check shows feedback at once, so one item's explanation would be on screen
    before the next item is answered, and could answer it (603 → 604, 610 → 611 to 613; #167
    review). Mastery items get explanations once #144 decides when the check shows feedback."""
    explained = [
        a.id
        for a in read_fixtures().activities
        if a.purpose == "mastery" and (a.solution or {}).get("explanation")
    ]
    assert explained == []


def test_every_module_practice_item_explains_its_answer() -> None:
    """A right answer to a practice item leads with why it is right (FeedbackPanel, #214), so
    every practice item a module shows, support items included, carries an explanation. Without
    one, a right answer says only "Correct."."""
    fixtures = read_fixtures()
    shown = {
        segment.activity_id
        for module in fixtures.modules
        for segment in module.segments
        if segment.activity_id is not None
    }
    practice = [a for a in fixtures.activities if a.purpose == "practice"]
    assert practice
    assert {a.id for a in practice} <= shown
    unexplained = [a.id for a in practice if not (a.solution or {}).get("explanation")]
    assert unexplained == []


def test_a_trace_may_carry_an_explanation_but_no_answer() -> None:
    """A trace keeps no stored answer (the engine derives it, FR-6.6), but its explanation is
    shown when the trace is right, like any other kind's."""
    validate_activity("trace", TRACE_CONFIG, {"explanation": "B finds A and D first."})
    with pytest.raises(ValueError, match="Extra inputs"):
        validate_activity("trace", TRACE_CONFIG, {"order": ["B", "A"]})


def test_choose_tests_text_never_names_a_test_by_its_stored_id() -> None:
    """The screen numbers the test cases ("Test 1: start at A") because an id such as
    `two-islands` names what the student has to spot. Hints, feedback and explanations must use the
    numbers too (#167 review)."""
    for a in read_fixtures().activities:
        if a.kind != "choose_tests":
            continue
        ids = [t["id"] for t in a.config["tests"] if "-" in t["id"]]  # the telling ones
        texts = [h.body for h in a.hints]
        texts += list((a.solution or {}).get("feedback", {}).values())
        texts.append((a.solution or {}).get("explanation") or "")
        for text in texts:
            assert not [i for i in ids if i in text], (a.id, text)


@pytest.mark.parametrize(
    ("kind", "submission"),
    [
        ("choose_tests", {"selected": [""]}),
        ("choose_tests", {"selected": [" ", ""]}),
        ("trace", {"rows": [{"visitedVertex": "", "queue": [], "visited": [], "order": []}]}),
        ("matching", {"pairs": {"a": ""}}),
        ("multiple_choice", {"selected": "  "}),
    ],
)
def test_answers_that_choose_nothing_are_blank(kind: str, submission: dict[str, Any]) -> None:
    """These answer nothing, so they are refused rather than recorded (#143, #165 review)."""
    assert is_blank(kind, submission)


def test_a_partly_filled_trace_is_not_blank() -> None:
    row = {"visitedVertex": "A", "queue": [], "visited": [], "order": []}
    assert not is_blank("trace", {"rows": [row]})
