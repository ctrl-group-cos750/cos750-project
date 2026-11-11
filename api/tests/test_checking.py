"""The code-activity checkers (app/services/checking.py). Pure comparison, no database, no code
execution: these mirror the grading a student submission gets."""

import pytest
from pydantic import ValidationError

from app.schemas.activities import (
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
