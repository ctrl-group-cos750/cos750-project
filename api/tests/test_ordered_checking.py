"""The ordered checkers with several accepted orders (app/services/checking.py, #145): groups of
interchangeable lines, alternative orders, and feedback that marks only the lines that must move
(FR-5.4). Fix the bug's cases are in test_activity_kinds.py."""

import time
from itertools import permutations

import pytest

from app.schemas.activities import CheckResult, ParsonsConfig, ParsonsSolution, ParsonsSubmission
from app.services import checking

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
