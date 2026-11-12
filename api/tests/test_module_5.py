"""Module 5 (Test and debug): the content fixture is correct.

Module 5 teaches students to find and fix bugs in BFS, and to choose test cases that expose
them.  These tests check:

- Content rules: every activity has four hint levels; level 4 starts with "Answer:"; every wrong
  answer / faulty line / test case has feedback.
- Retrieval: exactly 2, none placed in segments.
- Worked example: has skip_check_activity_id pointing at a valid practice activity (503).
- Segment coverage: every activity appears in exactly one segment or is a retrieval item.
- Objectives: the non-retrieval module-5 activities all cover objective 7.
- fix_the_bug (504, 505): the faulty program fails the hidden tests; the fixed program passes;
  every wrong correction leaves BFS broken.
- choose_tests (506, 507): every TestCase.expected matches the real BFS engine; the exposing set
  is exactly the tests the faulty code actually fails; both sets include "cycle" and "two-islands".

Patterns follow test_module_2.py (retrieval, worked example, skip check) and test_module_6.py
(fix_the_bug and choose_tests: run_bfs_code, passes_hidden, exposing-set verification).
"""

import signal
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType
from typing import Any

import pytest

from app.schemas.activities import FixTheBugSolution
from app.schemas.graphs import GraphEdge, GraphScenarioOut
from app.seed import ActivityFixture, FixtureFile, read_fixtures
from app.services.bfs import run_bfs

CONTENT: FixtureFile = read_fixtures()
MODULE = next(m for m in CONTENT.modules if m.id == 5)
ACTIVITIES = [a for a in CONTENT.activities if a.module_id == 5]

# ---------------------------------------------------------------------------
# The Graph class the code items run on (same as in test_module_6.py).
# ---------------------------------------------------------------------------

GRAPH = """
class Graph:
    def __init__(self, directed=False):
        self.directed = directed
        self.adjacency = {}

    def add_vertex(self, v):
        if v not in self.adjacency:
            self.adjacency[v] = []

    def add_edge(self, a, b):
        self.add_vertex(a)
        self.add_vertex(b)
        self.adjacency[a].append(b)
        if not self.directed:
            self.adjacency[b].append(a)
"""

# ---------------------------------------------------------------------------
# Hidden tests: the same representative suite used in test_module_6.py so
# that "passes the hidden tests" has the same meaning across modules.
# ---------------------------------------------------------------------------

HIDDEN: dict[str, tuple[bool, str, list[str], str]] = {
    # name: (directed, vertices, edges in the order they are added, start)
    "line": (False, "VWXYZ", ["ZY", "YX", "XW", "WV"], "X"),
    "cycle": (False, "ABCD", ["AB", "BC", "CD", "DA", "AC"], "A"),
    "sports-centre": (False, "ABCDEFG", ["AB", "AD", "BC", "BE", "DE", "EF", "CG", "FG"], "A"),
    "sports-centre-from-g": (
        False,
        "ABCDEFG",
        ["AB", "AD", "BC", "BE", "DE", "EF", "CG", "FG"],
        "G",
    ),
    "residence": (False, "PQRSTU", ["PQ", "PR", "QS", "RS", "RT", "SU", "TU"], "P"),
    "residence-from-u": (False, "PQRSTU", ["PQ", "PR", "QS", "RS", "RT", "SU", "TU"], "U"),
    "out-of-order": (False, "ABCDE", ["AE", "AC", "AB", "BD"], "A"),
    "two-islands": (False, "ABCDE", ["AB", "BC", "DE"], "A"),
    "one-way": (True, "ABCD", ["AB", "BC", "CA", "DA"], "A"),
}


# ---------------------------------------------------------------------------
# Helpers (mirror test_module_6.py).
# ---------------------------------------------------------------------------


def activity(activity_id: int) -> ActivityFixture:
    return next(a for a in ACTIVITIES if a.id == activity_id)


def scenario(directed: bool, vertices: Any, edges: Any, start: str) -> GraphScenarioOut:
    return GraphScenarioOut(
        id=0,
        name="",
        directed=directed,
        vertices=list(vertices),
        edges=[GraphEdge(source=e[0], target=e[1]) for e in edges],
        start_vertex=start,
    )


@contextmanager
def time_limit(seconds: float) -> Iterator[None]:
    """Stop a BFS that loops forever (a wrong line can empty and re-fill visited forever)."""

    def stop(signum: int, frame: FrameType | None) -> None:
        raise TimeoutError

    previous = signal.signal(signal.SIGALRM, stop)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _run(
    code: str,
    namespace: dict[str, Any],
    directed: bool,
    vertices: Any,
    edges: Any,
    start: str,
) -> Any:
    exec(GRAPH + "\n" + code, namespace)  # noqa: S102 - our own fixture code, in our own tests
    g = namespace["Graph"](directed=directed)
    for v in vertices:
        g.add_vertex(v)
    for source, target in edges:
        g.add_edge(source, target)
    return namespace["bfs"](g, start)


def run_bfs_code(code: str, directed: bool, vertices: Any, edges: Any, start: str) -> Any:
    """Run `bfs` in `code` on this graph; return the result or the exception (including
    TimeoutError for a loop that never terminates)."""
    namespace: dict[str, Any] = {}
    try:
        with time_limit(0.5):
            return _run(code, namespace, directed, vertices, edges, start)
    except Exception as exc:  # any error is a failing test
        return exc


def passes_hidden(code: str) -> bool:
    """Return True iff `code`'s `bfs` passes every hidden test."""
    for directed, vertices, edges, start in HIDDEN.values():
        want = run_bfs(scenario(directed, vertices, edges, start)).order
        if run_bfs_code(code, directed, vertices, edges, start) != want:
            return False
    return True


def first_order(a: ActivityFixture) -> list[int]:
    """One correct flat order of a fix_the_bug item's lines (groups in the order written)."""
    return FixTheBugSolution.model_validate(a.solution).first_order()


def lines_text(a: ActivityFixture, order: list[int]) -> str:
    """The code text for a fix_the_bug item given a flat list of line ids."""
    by_id = {x["id"]: x["text"] for x in a.config["lines"] + a.config.get("corrections", [])}
    return "\n".join(by_id[i] for i in order)


# ---------------------------------------------------------------------------
# Content rules.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("a", ACTIVITIES, ids=lambda a: str(a.id))
def test_every_activity_has_four_hint_levels_and_level_4_starts_with_answer(
    a: ActivityFixture,
) -> None:
    assert [h.level for h in a.hints] == [1, 2, 3, 4]
    assert a.hints[-1].body.startswith("Answer:")


@pytest.mark.parametrize("a", ACTIVITIES, ids=lambda a: str(a.id))
def test_every_wrong_answer_has_feedback(a: ActivityFixture) -> None:
    fb = a.solution.get("feedback", {})
    match a.kind:
        case "multiple_choice":
            wrong = {o["id"] for o in a.config["options"]} - {a.solution["correct"]}
            assert set(fb) == wrong
            # Three-part feedback: every message is non-empty (result + reason + next step).
            for opt_id in wrong:
                assert fb[opt_id], f"activity {a.id} option {opt_id} has empty feedback"
        case "fix_the_bug":
            faulty = {x["id"] for x in a.config["lines"]} - set(first_order(a))
            assert {int(k) for k in fb} == faulty
            for line_id in faulty:
                assert fb[str(line_id)], f"activity {a.id} line {line_id} has empty feedback"
        case "choose_tests":
            assert set(fb) == {t["id"] for t in a.config["tests"]}
            for test_id in fb:
                assert fb[test_id], f"activity {a.id} test {test_id} has empty feedback"


# ---------------------------------------------------------------------------
# Retrieval rules.
# ---------------------------------------------------------------------------


def test_retrieval_count_is_exactly_2_and_none_are_in_segments() -> None:
    retrieval = [a for a in ACTIVITIES if a.purpose == "retrieval"]
    assert len(retrieval) == 2
    segment_activity_ids = {s.activity_id for s in MODULE.segments if s.activity_id is not None}
    for a in retrieval:
        assert a.id not in segment_activity_ids, (
            f"retrieval activity {a.id} must not appear in segments"
        )


def test_retrieval_ids_are_501_and_502() -> None:
    retrieval_ids = sorted(a.id for a in ACTIVITIES if a.purpose == "retrieval")
    assert retrieval_ids == [501, 502]


# ---------------------------------------------------------------------------
# Segment coverage: every activity appears exactly once (segment or retrieval).
# ---------------------------------------------------------------------------


def test_every_activity_is_shown_by_exactly_one_segment_or_is_a_retrieval_item() -> None:
    shown = [s.activity_id for s in MODULE.segments if s.activity_id is not None]
    skip_checks = [
        s.skip_check_activity_id for s in MODULE.segments if s.skip_check_activity_id is not None
    ]
    retrieval = [a.id for a in ACTIVITIES if a.purpose == "retrieval"]
    assert sorted(shown + skip_checks + retrieval) == sorted(a.id for a in ACTIVITIES)


# ---------------------------------------------------------------------------
# Objectives.
# ---------------------------------------------------------------------------


# The course's closing transfer task (#87, Gagné event 9) ends module 5: BFS on a new problem, so it
# practises objectives 5 (the trace) and 4 (what the trace answers), not module 5's own objective.
CLOSING_TASK = {581, 582}


def test_non_retrieval_activities_cover_objective_7() -> None:
    non_retrieval = [a for a in ACTIVITIES if a.purpose != "retrieval" and a.id not in CLOSING_TASK]
    objectives = {a.objective_id for a in non_retrieval}
    # Every practice activity must target objective 7 (the module objective).
    assert objectives == {7}


def test_module_5_ends_with_the_closing_transfer_task() -> None:
    """Gagné event 9 (#87): a framing text, a trace on a new graph, then what the trace answers."""
    ids = {a.id: a for a in ACTIVITIES}
    assert {(ids[i].purpose, ids[i].objective_id) for i in CLOSING_TASK} == {
        ("practice", 5),
        ("practice", 4),
    }


# ---------------------------------------------------------------------------
# Worked example: skip-check wiring.
# ---------------------------------------------------------------------------


def test_worked_example_segment_has_skip_check_pointing_at_practice_503() -> None:
    worked = next((s for s in MODULE.segments if s.kind == "worked_example"), None)
    assert worked is not None, "module 5 has no worked_example segment"
    assert worked.skip_check_activity_id == 503
    # 503 must be a real practice activity in this module.
    skip_check_activity = next((a for a in ACTIVITIES if a.id == 503), None)
    assert skip_check_activity is not None
    assert skip_check_activity.purpose == "practice"


# ---------------------------------------------------------------------------
# fix_the_bug: faulty fails / fixed passes.
# ---------------------------------------------------------------------------

FIXES = [a for a in ACTIVITIES if a.kind == "fix_the_bug"]


@pytest.mark.parametrize("a", FIXES, ids=lambda a: str(a.id))
def test_the_faulty_program_fails_and_the_fixed_program_passes(a: ActivityFixture) -> None:
    original = [x["id"] for x in a.config["lines"]]
    assert not passes_hidden(lines_text(a, original)), (
        f"activity {a.id}: faulty program unexpectedly passes all hidden tests"
    )
    assert passes_hidden(lines_text(a, first_order(a))), (
        f"activity {a.id}: fixed program fails a hidden test"
    )


# ---------------------------------------------------------------------------
# fix_the_bug: every wrong correction leaves BFS broken.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("a", FIXES, ids=lambda a: str(a.id))
def test_each_wrong_correction_leaves_bfs_broken(a: ActivityFixture) -> None:
    order = first_order(a)
    used = [c for c in a.config["corrections"] if c["id"] in order]
    unused = [c for c in a.config["corrections"] if c["id"] not in order]
    assert unused, f"activity {a.id}: no wrong corrections to test"
    if not used:
        # Fix is pure deletion (no replacement corrections in the solution).
        # Verify that each distractor, when inserted after the correct deletion-only
        # program, still causes BFS to fail the hidden suite.
        for wrong in unused:
            appended = [*first_order(a), wrong["id"]]
            assert not passes_hidden(lines_text(a, appended)), (
                f"activity {a.id}: distractor correction '{wrong['text']}' "
                "inserted after fixed program still passes all hidden tests"
            )
    else:
        for wrong in unused:
            for right in used:
                swapped = [wrong["id"] if i == right["id"] else i for i in order]
                assert not passes_hidden(lines_text(a, swapped)), (
                    f"activity {a.id}: wrong correction '{wrong['text']}' replacing "
                    f"'{right['text']}' still passes all hidden tests"
                )


# ---------------------------------------------------------------------------
# choose_tests: expected arrays match the engine.
# ---------------------------------------------------------------------------

CHOICES = [a for a in ACTIVITIES if a.kind == "choose_tests"]


@pytest.mark.parametrize("a", CHOICES, ids=lambda a: str(a.id))
def test_every_test_case_expected_matches_the_bfs_engine(a: ActivityFixture) -> None:
    for t in a.config["tests"]:
        edges = [(e["source"], e["target"]) for e in t["edges"]]
        reference = run_bfs(scenario(t["directed"], t["vertices"], edges, t["start_vertex"])).order
        assert t["expected"] == reference, (
            f"activity {a.id} test '{t['id']}': expected {t['expected']}, engine says {reference}"
        )


# ---------------------------------------------------------------------------
# choose_tests: exposing set = exactly the tests the faulty code actually fails.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("a", CHOICES, ids=lambda a: str(a.id))
def test_exposing_set_is_exactly_the_tests_the_faulty_code_fails(
    a: ActivityFixture,
) -> None:
    fails = []
    for t in a.config["tests"]:
        edges = [(e["source"], e["target"]) for e in t["edges"]]
        reference = run_bfs(scenario(t["directed"], t["vertices"], edges, t["start_vertex"])).order
        got = run_bfs_code(a.config["code"], t["directed"], t["vertices"], edges, t["start_vertex"])
        if got != reference:
            fails.append(t["id"])
    assert sorted(fails) == sorted(a.solution["exposing"]), (
        f"activity {a.id}: faulty code fails {sorted(fails)}, "
        f"but exposing set is {sorted(a.solution['exposing'])}"
    )


# ---------------------------------------------------------------------------
# choose_tests: both activities include "cycle" and "two-islands" test ids.
# ---------------------------------------------------------------------------


def test_both_choose_tests_activities_include_cycle_and_two_islands() -> None:
    assert len(CHOICES) == 2, f"expected 2 choose_tests activities, got {len(CHOICES)}"
    for a in CHOICES:
        test_ids = {t["id"] for t in a.config["tests"]}
        assert "cycle" in test_ids, f"activity {a.id} choose_tests has no 'cycle' test case"
        assert "two-islands" in test_ids, (
            f"activity {a.id} choose_tests has no 'two-islands' test case"
        )
