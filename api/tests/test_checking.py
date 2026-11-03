"""The code-activity checkers (app/services/checking.py). Pure comparison, no database, no code
execution: these mirror the grading a student submission gets."""

import pytest

from app.schemas.activities import (
    FillInConfig,
    FillInSolution,
    FillInSubmission,
    ParsonsConfig,
    ParsonsSolution,
    ParsonsSubmission,
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


def test_parsons_two_lines_swapped_fails_both_positions() -> None:
    result = checking.check_parsons(PARSONS, PARSONS_SOLUTION, ParsonsSubmission(order=[1, 0, 2]))
    assert not result.correct
    assert result.score == pytest.approx(1 / 3)
    assert [p.correct for p in result.parts] == [False, False, True]
    assert result.parts[0].message == checking.OUT_OF_PLACE


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


def test_fill_in_missing_blank_is_reported_empty() -> None:
    result = checking.check_fill_in(
        FILL_IN, FILL_IN_SOLUTION, FillInSubmission(answers={1: "start"})
    )
    assert not result.correct
    assert result.parts[1].message == checking.EMPTY_BLANK


def test_dispatch_parsons_from_plain_data() -> None:
    result = checking.check_code_activity(
        "parsons",
        {"lines": [{"id": 0, "text": "a"}, {"id": 1, "text": "b"}]},
        {"order": [0, 1]},
        {"order": [0, 1]},
    )
    assert result.correct


def test_dispatch_fill_in_from_plain_data() -> None:
    result = checking.check_code_activity(
        "fill_in",
        {"code": "x = __1__", "blanks": [1], "options": ["1", "2"]},
        {"answers": {"1": "1"}},
        {"answers": {"1": "2"}},
    )
    assert not result.correct
    assert result.parts[0].message == checking.WRONG_CHOICE


def test_dispatch_unknown_kind_raises() -> None:
    with pytest.raises(ValueError, match="unknown code activity kind"):
        checking.check_code_activity("freeform", {}, {}, {})
