"""The code-activity checkers (app/services/checking.py). Pure comparison, no database, no code
execution: these mirror the grading a student submission gets."""

import time
from itertools import permutations

import pytest
from pydantic import ValidationError

from app.schemas.activities import (
    CheckResult,
    FillInConfig,
    FillInSolution,
    FillInSubmission,
    MultipleChoiceConfig,
    MultipleChoiceSolution,
    MultipleChoiceSubmission,
    ParsonsConfig,
    ParsonsSolution,
    ParsonsSubmission,
    TraceConfig,
    TraceSubmission,
)
from app.services import checking

# A small Parsons problem: three real lines (0, 1, 2) and one distractor (9).
PARSONS = ParsonsConfig.model_validate(
    {
        "lines": [
            {"id": 0, "text": "def bfs(graph, start):"},
            {"id": 1, "text": "    queue = [start]"},
            {"id": 2, "text": "    return order"},
            {"id": 9, "text": "    graph.sort()  # distractor"},
        ]
    }
)
PARSONS_SOLUTION = ParsonsSolution(order=[0, 1, 2])


def test_parsons_correct_order_passes() -> None:
    result = checking.check_parsons(PARSONS, PARSONS_SOLUTION, ParsonsSubmission(order=[0, 1, 2]))
    assert result.correct
    assert result.score == 1.0
    assert [p.correct for p in result.parts] == [True, True, True]


def test_parsons_two_lines_swapped_marks_one_line_to_move() -> None:
    # Moving either line fixes it, so only one is marked; position-by-position marked both.
    result = checking.check_parsons(PARSONS, PARSONS_SOLUTION, ParsonsSubmission(order=[1, 0, 2]))
    assert not result.correct
    assert result.score == pytest.approx(2 / 3)
    assert [p.correct for p in result.parts].count(False) == 1
    assert next(p for p in result.parts if not p.correct).message == checking.OUT_OF_PLACE


def test_parsons_distractor_line_used_is_marked_as_not_belonging() -> None:
    result = checking.check_parsons(PARSONS, PARSONS_SOLUTION, ParsonsSubmission(order=[0, 9, 2]))
    assert not result.correct
    assert result.parts[1].message == checking.EXTRA_LINE


def test_parsons_extra_trailing_line_lowers_the_score() -> None:
    result = checking.check_parsons(
        PARSONS, PARSONS_SOLUTION, ParsonsSubmission(order=[0, 1, 2, 9])
    )
    assert not result.correct
    assert len(result.parts) == 4
    assert result.parts[3].message == checking.EXTRA_LINE
    assert result.score == pytest.approx(3 / 4)


def test_parsons_short_answer_reports_a_missing_line() -> None:
    result = checking.check_parsons(PARSONS, PARSONS_SOLUTION, ParsonsSubmission(order=[0, 1]))
    assert not result.correct
    assert result.parts[2].message == checking.MISSING_LINE


def test_parsons_empty_submission_scores_zero() -> None:
    result = checking.check_parsons(PARSONS, PARSONS_SOLUTION, ParsonsSubmission(order=[]))
    assert result.score == 0.0
    assert all(not p.correct for p in result.parts)


FILL_IN = FillInConfig(
    code="queue = [__1__]\nvisited = __2__",
    blanks=[1, 2],
    options=["start", "set()", "[]", "0"],
)
FILL_IN_SOLUTION = FillInSolution(answers={1: "start", 2: "set()"})


def test_fill_in_all_tokens_correct_passes() -> None:
    result = checking.check_fill_in(
        FILL_IN, FILL_IN_SOLUTION, FillInSubmission(answers={1: "start", 2: "set()"})
    )
    assert result.correct
    assert result.score == 1.0


def test_fill_in_wrong_token_fails_that_blank() -> None:
    result = checking.check_fill_in(
        FILL_IN, FILL_IN_SOLUTION, FillInSubmission(answers={1: "start", 2: "[]"})
    )
    assert not result.correct
    assert result.score == pytest.approx(1 / 2)
    assert result.parts[1].message == checking.WRONG_CHOICE


def test_fill_in_wrong_token_gets_the_contents_reason_for_it() -> None:
    reason = "Not quite. visited starts empty: nothing has been visited yet."
    solution = FillInSolution(answers={1: "start", 2: "set()"}, feedback={2: {"[]": reason}})
    result = checking.check_fill_in(
        FILL_IN, solution, FillInSubmission(answers={1: "start", 2: "[]"})
    )
    assert result.parts[1].message == reason
    # Another wrong token on the same blank, and a wrong token on a blank with no feedback, still
    # get the generic message.
    other = checking.check_fill_in(FILL_IN, solution, FillInSubmission(answers={1: "0", 2: "0"}))
    assert [p.message for p in other.parts] == [checking.WRONG_CHOICE, checking.WRONG_CHOICE]


def test_fill_in_right_answers_never_carry_a_message() -> None:
    solution = FillInSolution(answers={1: "start", 2: "set()"}, feedback={2: {"[]": "reason"}})
    result = checking.check_fill_in(
        FILL_IN, solution, FillInSubmission(answers={1: "start", 2: "set()"})
    )
    assert result.correct
    assert all(p.message is None for p in result.parts)


def test_fill_in_missing_blank_is_reported_empty() -> None:
    result = checking.check_fill_in(
        FILL_IN, FILL_IN_SOLUTION, FillInSubmission(answers={1: "start"})
    )
    assert not result.correct
    assert result.parts[1].message == checking.EMPTY_BLANK


def test_dispatch_parsons_from_plain_data() -> None:
    result = checking.check_activity(
        "parsons",
        {"lines": [{"id": 0, "text": "a"}, {"id": 1, "text": "b"}]},
        {"order": [0, 1]},
        {"order": [0, 1]},
    )
    assert result.correct


def test_dispatch_fill_in_from_plain_data() -> None:
    result = checking.check_activity(
        "fill_in",
        {"code": "x = __1__", "blanks": [1], "options": ["1", "2"]},
        {"answers": {"1": "1"}},
        {"answers": {"1": "2"}},
    )
    assert not result.correct
    assert result.parts[0].message == checking.WRONG_CHOICE


def test_dispatch_fill_in_feedback_from_json_keys() -> None:
    # Fixtures are JSON, so blank ids arrive as strings; they must still find their message.
    result = checking.check_activity(
        "fill_in",
        {"code": "x = __1__", "blanks": [1], "options": ["1", "2"]},
        {"answers": {"1": "1"}, "feedback": {"1": {"2": "Not quite: x starts at 1."}}},
        {"answers": {"1": "2"}},
    )
    assert result.parts[0].message == "Not quite: x starts at 1."


def test_dispatch_unknown_kind_raises() -> None:
    with pytest.raises(ValueError, match="unknown activity kind"):
        checking.check_activity("freeform", {}, {}, {})


# --- Hardening: the checker is the untrusted boundary now, so malformed input must be graded,
# --- never crash, and the solution must never leak into the result.


def test_parsons_config_requires_at_least_one_line() -> None:
    with pytest.raises(ValidationError):
        ParsonsConfig.model_validate({"lines": []})


def test_parsons_config_rejects_too_many_lines() -> None:
    with pytest.raises(ValidationError):
        ParsonsConfig.model_validate({"lines": [{"id": i, "text": "x"} for i in range(101)]})


def test_fill_in_config_requires_blanks_and_options() -> None:
    with pytest.raises(ValidationError):
        FillInConfig.model_validate({"code": "x", "blanks": [], "options": ["a"]})
    with pytest.raises(ValidationError):
        FillInConfig.model_validate({"code": "x", "blanks": [1], "options": []})


def test_parsons_duplicate_ids_in_a_submission_are_graded_by_position_not_crash() -> None:
    result = checking.check_parsons(PARSONS, PARSONS_SOLUTION, ParsonsSubmission(order=[0, 0, 2]))
    assert [p.correct for p in result.parts] == [True, False, True]
    assert result.parts[1].message == checking.OUT_OF_PLACE


def test_parsons_unknown_line_id_in_submission_is_marked_as_not_belonging() -> None:
    result = checking.check_parsons(PARSONS, PARSONS_SOLUTION, ParsonsSubmission(order=[0, 7, 2]))
    assert result.parts[1].message == checking.EXTRA_LINE  # 7 isn't even a line in this activity


def test_fill_in_ignores_submitted_blanks_that_are_not_in_the_activity() -> None:
    result = checking.check_fill_in(
        FILL_IN, FILL_IN_SOLUTION, FillInSubmission(answers={1: "start", 2: "set()", 99: "junk"})
    )
    assert result.correct  # the stray blank 99 is ignored; only configured blanks are graded
    assert [p.ref for p in result.parts] == [1, 2]


def test_the_result_never_contains_the_solution() -> None:
    # Even a fully wrong answer: the response the API would send carries no solution token.
    result = checking.check_fill_in(
        FILL_IN, FILL_IN_SOLUTION, FillInSubmission(answers={1: "wrong", 2: "wrong"})
    )
    blob = result.model_dump_json()
    assert "start" not in blob
    assert "set()" not in blob


# --- Multiple choice ---------------------------------------------------------------------------

CHOICE = MultipleChoiceConfig.model_validate(
    {
        "prompt": "Which leaves the queue?",
        "options": [
            {"id": "a", "label": "A"},
            {"id": "c", "label": "C"},
            {"id": "z", "label": "Z"},
        ],
    }
)
CHOICE_SOLUTION = MultipleChoiceSolution(correct="a", feedback={"c": "C was added last."})


def test_multiple_choice_right_option_passes() -> None:
    result = checking.check_multiple_choice(
        CHOICE, CHOICE_SOLUTION, MultipleChoiceSubmission(selected="a")
    )
    assert result.correct
    assert result.score == 1.0


def test_multiple_choice_wrong_option_says_why() -> None:
    result = checking.check_multiple_choice(
        CHOICE, CHOICE_SOLUTION, MultipleChoiceSubmission(selected="c")
    )
    assert not result.correct
    assert result.feedback == "C was added last."
    assert '"a"' not in result.model_dump_json()  # the correct option is never named


def test_multiple_choice_wrong_option_without_feedback_gets_the_generic_message() -> None:
    result = checking.check_multiple_choice(
        CHOICE, CHOICE_SOLUTION, MultipleChoiceSubmission(selected="z")
    )
    assert result.feedback == checking.WRONG_OPTION


def test_multiple_choice_unknown_option_is_wrong_not_a_crash() -> None:
    result = checking.check_multiple_choice(
        CHOICE, CHOICE_SOLUTION, MultipleChoiceSubmission(selected="nope")
    )
    assert not result.correct
    assert result.feedback == checking.UNKNOWN_OPTION


def test_dispatch_multiple_choice_from_plain_data() -> None:
    result = checking.check_activity(
        "multiple_choice",
        CHOICE.model_dump(),
        CHOICE_SOLUTION.model_dump(),
        {"selected": "a"},
    )
    assert result.correct


# --- Trace table: checked step by step against the BFS engine (FR-6.6) -------------------------

# Undirected A-B, A-C, B-D, start A. Neighbours alphabetical, so BFS visits A, B, C, D.
TRACE = TraceConfig.model_validate(
    {
        "directed": False,
        "vertices": ["A", "B", "C", "D"],
        "edges": [
            {"source": "A", "target": "B"},
            {"source": "A", "target": "C"},
            {"source": "B", "target": "D"},
        ],
        "start_vertex": "A",
    }
)
# The correct trace (the state after each step), matching the engine.
CORRECT_ROWS = [
    {"visited_vertex": "A", "queue": ["B", "C"], "visited": ["A"], "order": ["A"]},
    {"visited_vertex": "B", "queue": ["C", "D"], "visited": ["A", "B"], "order": ["A", "B"]},
    {"visited_vertex": "C", "queue": ["D"], "visited": ["A", "B", "C"], "order": ["A", "B", "C"]},
    {
        "visited_vertex": "D",
        "queue": [],
        "visited": ["A", "B", "C", "D"],
        "order": ["A", "B", "C", "D"],
    },
]


def test_trace_correct_matches_the_engine_step_by_step() -> None:
    result = checking.check_trace(TRACE, TraceSubmission.model_validate({"rows": CORRECT_ROWS}))
    assert result.correct
    assert result.score == 1.0
    assert [p.correct for p in result.parts] == [True, True, True, True]


def test_trace_wrong_queue_fails_only_that_step() -> None:
    rows = [dict(r) for r in CORRECT_ROWS]
    rows[1] = {**rows[1], "queue": ["D", "C"]}  # right vertices, wrong order
    result = checking.check_trace(TRACE, TraceSubmission.model_validate({"rows": rows}))
    assert not result.correct
    assert result.score == pytest.approx(3 / 4)
    assert [p.correct for p in result.parts] == [True, False, True, True]
    assert result.parts[1].message == checking.WRONG_TRACE_STEP


def test_trace_wrong_visited_vertex_fails_that_step() -> None:
    rows = [dict(r) for r in CORRECT_ROWS]
    rows[2] = {**rows[2], "visited_vertex": "D"}  # visited D before C
    result = checking.check_trace(TRACE, TraceSubmission.model_validate({"rows": rows}))
    assert result.parts[2].message == checking.WRONG_TRACE_STEP


def test_trace_visited_set_is_compared_regardless_of_order() -> None:
    rows = [dict(r) for r in CORRECT_ROWS]
    rows[1] = {**rows[1], "visited": ["B", "A"]}  # same set as ["A", "B"]
    result = checking.check_trace(TRACE, TraceSubmission.model_validate({"rows": rows}))
    assert result.correct


def test_trace_visited_set_with_a_repeated_vertex_is_wrong() -> None:
    rows = [dict(r) for r in CORRECT_ROWS]
    rows[1] = {**rows[1], "visited": ["A", "B", "B"]}
    result = checking.check_trace(TRACE, TraceSubmission.model_validate({"rows": rows}))
    assert [p.correct for p in result.parts] == [True, False, True, True]


def test_trace_order_still_counts_order() -> None:
    rows = [dict(r) for r in CORRECT_ROWS]
    rows[1] = {**rows[1], "order": ["B", "A"]}  # the visit order is a sequence, not a set
    result = checking.check_trace(TRACE, TraceSubmission.model_validate({"rows": rows}))
    assert [p.correct for p in result.parts] == [True, False, True, True]


def test_trace_refuses_an_overlong_vertex_label() -> None:
    row = {"visited_vertex": "A" * 33, "queue": [], "visited": [], "order": []}
    with pytest.raises(ValidationError):
        TraceSubmission.model_validate({"rows": [row]})


def test_trace_config_refuses_a_bad_vertex_label() -> None:
    with pytest.raises(ValidationError):
        TraceConfig.model_validate(
            {"directed": False, "vertices": ["A b!"], "edges": [], "start_vertex": "A b!"}
        )


def test_trace_short_answer_reports_the_missing_steps() -> None:
    result = checking.check_trace(TRACE, TraceSubmission.model_validate({"rows": CORRECT_ROWS[:2]}))
    assert not result.correct
    assert len(result.parts) == 4
    assert result.parts[2].message == checking.MISSING_TRACE_STEP
    assert result.parts[3].message == checking.MISSING_TRACE_STEP
    assert result.score == pytest.approx(2 / 4)


def test_trace_extra_steps_lower_the_score() -> None:
    extra = [
        *CORRECT_ROWS,
        {"visited_vertex": "A", "queue": [], "visited": ["A", "B", "C", "D"], "order": ["A"]},
    ]
    result = checking.check_trace(TRACE, TraceSubmission.model_validate({"rows": extra}))
    assert not result.correct
    assert len(result.parts) == 5
    assert result.parts[4].message == checking.EXTRA_TRACE_STEP


def test_trace_empty_submission_scores_zero() -> None:
    result = checking.check_trace(TRACE, TraceSubmission.model_validate({"rows": []}))
    assert result.score == 0.0
    assert all(not p.correct for p in result.parts)


def test_dispatch_trace_from_plain_data_ignores_any_solution() -> None:
    result = checking.check_activity(
        "trace",
        TRACE.model_dump(),
        {},  # trace keeps no stored solution; the engine derives the answer
        {"rows": CORRECT_ROWS},
    )
    assert result.correct


def test_trace_bad_stored_graph_raises_not_silently_passes() -> None:
    # A content-authoring bug (start vertex not in the graph) must surface, not grade as correct.
    bad = {
        "directed": False,
        "vertices": ["A", "B"],
        "edges": [],
        "start_vertex": "Z",
    }
    with pytest.raises(ValueError, match="start vertex"):
        checking.check_activity("trace", bad, {}, {"rows": []})


# --- Several accepted orders (FR-5.4, #145) -------------------------------------------------------

# A BFS like module 4's: 1 import, 2 def, 3-5 the starting values, 6 while, 7 popleft, 8 order.append,
# 9 for, 10 if, 11 visited.add, 12 queue.append, 13 return. 20 is a distractor. The alternative (8 after
# the loop) only tests `alternatives`: the fixtures leave it out (module 3 records on dequeue).
BFS = ParsonsConfig.model_validate(
    {"lines": [{"id": i, "text": f"line {i}"} for i in [*range(1, 14), 20]]}
)
BFS_SOLUTION = ParsonsSolution.model_validate(
    {
        "order": [1, 2, [3, 4, 5], 6, 7, 8, 9, 10, [11, 12], 13],
        "alternatives": [[1, 2, [3, 4, 5], 6, 7, 9, 10, [11, 12], 8, 13]],
    }
)
REFERENCE = list(range(1, 14))


def check_bfs(order: list[int]) -> CheckResult:
    return checking.check_parsons(BFS, BFS_SOLUTION, ParsonsSubmission(order=order))


def wrong_positions(result: CheckResult) -> list[int]:
    return [p.ref for p in result.parts if not p.correct]


@pytest.mark.parametrize("start", list(permutations([3, 4, 5])))
@pytest.mark.parametrize("found", [(11, 12), (12, 11)])
@pytest.mark.parametrize("record_late", [False, True])
def test_every_accepted_bfs_order_is_fully_correct(
    start: tuple[int, ...], found: tuple[int, ...], record_late: bool
) -> None:
    loop = [9, 10, *found, 8] if record_late else [8, 9, 10, *found]
    result = check_bfs([1, 2, *start, 6, 7, *loop, 13])
    assert result.correct
    assert result.score == 1.0
    assert result.feedback == "All correct."
    assert len(result.parts) == 13
    assert all(p.correct for p in result.parts)


def test_a_plain_order_still_accepts_only_itself() -> None:
    # Content written before groups existed keeps its meaning: one order, nothing else.
    plain = ParsonsSolution.model_validate({"order": REFERENCE})
    config = ParsonsConfig.model_validate({"lines": [{"id": i, "text": "x"} for i in REFERENCE]})
    assert checking.check_parsons(config, plain, ParsonsSubmission(order=REFERENCE)).correct
    swapped = [1, 2, 4, 3, *REFERENCE[4:]]
    assert not checking.check_parsons(config, plain, ParsonsSubmission(order=swapped)).correct


def test_one_line_moved_early_is_the_only_line_marked() -> None:
    # return order at the top: by position every line would be wrong.
    result = check_bfs([13, *REFERENCE[:-1]])
    assert not result.correct
    assert wrong_positions(result) == [0]
    assert result.parts[0].message == checking.OUT_OF_PLACE
    assert result.feedback == "12 of 13 correct."


def test_one_line_moved_late_is_the_only_line_marked() -> None:
    # return inside the while loop's place (before the neighbour loop): only `return` moves.
    result = check_bfs([1, 2, 3, 4, 5, 6, 7, 8, 13, 9, 10, 11, 12])
    assert wrong_positions(result) == [8]


def test_a_group_out_of_its_place_is_marked_not_its_neighbours() -> None:
    # visited = {start} after the while line: the starting values may swap, not leave the start.
    result = check_bfs([1, 2, 4, 5, 6, 3, 7, 8, 9, 10, 11, 12, 13])
    assert wrong_positions(result) == [5]


def test_lines_swapped_within_a_group_and_a_mistake_elsewhere() -> None:
    # The student's group order is kept (it is accepted); only the real mistake is marked.
    result = check_bfs([1, 2, 5, 4, 3, 6, 8, 7, 9, 10, 12, 11, 13])
    assert len(wrong_positions(result)) == 1
    assert wrong_positions(result)[0] in (6, 7)  # popleft and order.append(v) swapped


def test_the_closest_accepted_order_is_used_for_feedback() -> None:
    # order.append(v) after the loop (the alternative) with the found lines in the wrong place:
    # compared with the alternative, only the misplaced if-line is wrong.
    result = check_bfs([1, 2, 3, 4, 5, 6, 7, 9, 11, 12, 10, 8, 13])
    assert not result.correct
    assert wrong_positions(result) == [10]  # against `order`, 8 would be marked too


def test_a_distractor_in_place_of_a_line_is_marked_as_not_belonging() -> None:
    result = check_bfs([1, 2, 3, 4, 5, 6, 20, 8, 9, 10, 11, 12, 13])
    assert wrong_positions(result) == [6]
    assert result.parts[6].message == checking.EXTRA_LINE


def test_a_distractor_added_to_a_right_answer_fails() -> None:
    result = check_bfs([*REFERENCE, 20])
    assert not result.correct
    assert wrong_positions(result) == [13]
    assert result.parts[13].message == checking.EXTRA_LINE


def test_a_short_answer_gets_a_missing_part_per_line_short() -> None:
    result = check_bfs([1, 2, 3])
    assert not result.correct
    assert [p.ref for p in result.parts] == list(range(13))
    assert [p.message for p in result.parts[3:]] == [checking.MISSING_LINE] * 10
    assert result.score == pytest.approx(3 / 13)


def test_an_empty_answer_scores_zero() -> None:
    result = check_bfs([])
    assert not result.correct
    assert result.score == 0.0
    assert len(result.parts) == 13


def test_a_line_used_twice_cannot_pass() -> None:
    # The group [3, 4, 5] filled with 3 three times: one 3 counts, the others are wrong.
    result = check_bfs([1, 2, 3, 3, 3, *REFERENCE[5:]])
    assert not result.correct
    assert wrong_positions(result) == [3, 4]


def test_every_line_repeated_cannot_pass() -> None:
    result = check_bfs([1] * 100)
    assert not result.correct
    assert len(result.parts) == 100
    assert sum(p.correct for p in result.parts) == 1


def test_junk_ids_are_not_belonging() -> None:
    result = check_bfs([-1, 0, 10**12, *REFERENCE])
    assert not result.correct
    assert wrong_positions(result) == [0, 1, 2]
    assert {result.parts[i].message for i in (0, 1, 2)} == {checking.EXTRA_LINE}


def test_a_reversed_answer_keeps_only_the_group() -> None:
    result = check_bfs(REFERENCE[::-1])
    # Reversed, the group's three lines are still in an order it accepts; nothing else is.
    assert not result.correct
    assert sum(p.correct for p in result.parts) == 3


def test_a_full_size_problem_is_checked_quickly() -> None:
    # 100 lines (the most a config allows) against 20 alternatives: the O(n^2) comparison is cheap.
    order = list(range(100))
    config = ParsonsConfig.model_validate({"lines": [{"id": i, "text": "x"} for i in order]})
    solution = ParsonsSolution.model_validate(
        {"order": order, "alternatives": [order[::-1][:k] + order[k:] for k in range(2, 22)]}
    )
    started = time.perf_counter()
    result = checking.check_parsons(config, solution, ParsonsSubmission(order=order[::-1]))
    assert time.perf_counter() - started < 1.0
    assert not result.correct


def test_dispatch_parsons_groups_from_plain_json() -> None:
    result = checking.check_activity(
        "parsons",
        {"lines": [{"id": 1, "text": "a"}, {"id": 2, "text": "b"}, {"id": 3, "text": "c"}]},
        {"order": [[1, 2], 3]},
        {"order": [2, 1, 3]},
    )
    assert result.correct


def test_a_missing_line_is_named_in_the_summary() -> None:
    # No line on screen can show a missing one, so the summary says it (#145 review).
    result = check_bfs([1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13])
    assert not result.correct
    assert all(p.correct for p in result.parts[:12])
    assert (
        result.feedback == "12 of 13 correct. 1 line is missing: add it from the available lines."
    )
    two = check_bfs([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13])
    assert two.feedback.endswith("2 lines are missing: add them from the available lines.")
