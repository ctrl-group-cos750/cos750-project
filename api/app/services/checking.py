"""Grades a submission by comparing it with the solution — never by running code (SE document
FR-4.2, FR-5, NFR-S7). One function per kind; `check_activity` dispatches by kind.

The solution stays here, on the server, and is only ever compared against: it is never returned to
the browser, so a student cannot read it or fake a pass.
"""

from typing import Any

from app.schemas.activities import (
    CheckResult,
    ChooseTestsConfig,
    ChooseTestsSolution,
    ChooseTestsSubmission,
    FillInConfig,
    FillInSolution,
    FillInSubmission,
    FixTheBugConfig,
    FixTheBugSolution,
    FixTheBugSubmission,
    MatchingConfig,
    MatchingSolution,
    MatchingSubmission,
    MultipleChoiceConfig,
    MultipleChoiceSolution,
    MultipleChoiceSubmission,
    ParsonsConfig,
    ParsonsSolution,
    ParsonsStep,
    ParsonsSubmission,
    PartResult,
    TraceConfig,
    TraceSubmission,
)
from app.schemas.graphs import GraphScenarioOut
from app.services.bfs import run_bfs

OUT_OF_PLACE = "This line is in the wrong place."
MISSING_LINE = "A line is missing from this position."
EXTRA_LINE = "This line does not belong in the answer."
WRONG_CHOICE = "This is not the right choice for this blank."
EMPTY_BLANK = "This blank has not been filled in."
WRONG_OPTION = "That is not the right answer. Have another look."
UNKNOWN_OPTION = "Choose one of the options."
RIGHT_OPTION = "Correct."
WRONG_MATCH = "This is not the right match."
NO_MATCH = "This item has not been matched."
BUG_LEFT_IN = "This line still has the bug. Replace it with one of the corrections."
WRONG_FIX = "This correction does not fix the bug here."
FIX_NOT_NEEDED = "This line was already right: it did not need a correction."
MISSED_TEST = "The faulty version fails this test: it exposes the bug."
NOT_EXPOSING = "The faulty version passes this test, so it does not expose the bug."
UNKNOWN_TEST = "This is not one of the test cases."
WRONG_TRACE_STEP = "This step does not match the traversal."
MISSING_TRACE_STEP = "The traversal has more steps than this."
EXTRA_TRACE_STEP = "The traversal is already finished by this step."


def _result(parts: list[PartResult]) -> CheckResult:
    total = len(parts)
    right = sum(1 for part in parts if part.correct)
    correct = total > 0 and right == total
    feedback = "All correct." if correct else f"{right} of {total} correct."
    return CheckResult(
        correct=correct, score=right / total if total else 0.0, parts=parts, feedback=feedback
    )


def _closest(steps: list[ParsonsStep], got: list[int]) -> list[int]:
    """The order `steps` accepts that is closest to `got`: each group's lines in the order the
    student put them (lines of a group the student left out go last, as written). No order the
    steps accept keeps more of `got` in place, so this is the one to compare with."""
    first: dict[int, int] = {}
    for i, line in enumerate(got):
        first.setdefault(line, i)
    order: list[int] = []
    for step in steps:
        if isinstance(step, int):
            order.append(step)
        else:
            order.extend(sorted(step, key=lambda line: first.get(line, len(got))))
    return order


def _in_sequence(expected: list[int], got: list[int]) -> set[int]:
    """The positions in `got` of a longest run of lines already in `expected`'s relative order
    (a longest common subsequence; ids in `expected` are distinct). Those lines can stay where
    they are; every other line has to move, so only they are marked wrong. A line used twice
    counts once. O(n²) for n ≤ 100 lines."""
    rank = {line: r for r, line in enumerate(expected)}
    ranked = [(i, rank[line]) for i, line in enumerate(got) if line in rank]
    best: list[int] = []  # best[k]: length of the longest run ending at ranked[k]
    back: list[int] = []  # the run's previous entry, or -1
    for k, (_, r) in enumerate(ranked):
        best.append(1)
        back.append(-1)
        for j in range(k):
            if ranked[j][1] < r and best[j] + 1 > best[k]:
                best[k], back[k] = best[j] + 1, j
    kept: set[int] = set()
    k = max(range(len(ranked)), key=lambda k: best[k], default=-1)
    while k != -1:
        kept.add(ranked[k][0])
        k = back[k]
    return kept


def check_parsons(
    config: ParsonsConfig, solution: ParsonsSolution, submission: ParsonsSubmission
) -> CheckResult:
    """Correct when the order is any the solution accepts (FR-5.4): its `order` or an
    `alternative`, with the lines of each group in any order among themselves.

    The feedback compares the student's order with the closest accepted order by relative order,
    not position: the lines of a longest common subsequence stay, the rest are marked. So one
    line in the wrong place is the only line marked wrong, instead of every line after it. The
    Parsons reviews (Du et al. 2020; Ericson et al. 2022) set line-order grading against
    execution-based grading; this keeps line order but accepts every order the content lists.

    There is one part per position of the answer, as before: right if the line there is in that
    longest run, otherwise "in the wrong place" (a solution line, or one used twice) or "does not
    belong" (a distractor, or an id not in the activity). If the answer is shorter than the
    solution, a "missing" part per line short follows, so a short answer cannot pass and its
    score shows how much is missing. All parts right means the answer is exactly an accepted
    order. `config` is accepted for a uniform checker signature; grading needs only the
    solution."""
    got = submission.order
    closest: list[int] = []
    kept: set[int] = set()
    for n, steps in enumerate(solution.accepted()):  # `order` first, so it wins a tie
        candidate = _closest(steps, got)
        in_order = _in_sequence(candidate, got)
        if n == 0 or len(in_order) > len(kept):
            closest, kept = candidate, in_order
    in_solution = set(closest)
    parts: list[PartResult] = []
    for i, have in enumerate(got):
        if i in kept:
            parts.append(PartResult(ref=i, correct=True))
        else:
            message = OUT_OF_PLACE if have in in_solution else EXTRA_LINE
            parts.append(PartResult(ref=i, correct=False, message=message))
    parts.extend(
        PartResult(ref=i, correct=False, message=MISSING_LINE)
        for i in range(len(got), len(closest))
    )
    return _result(parts)


def check_fill_in(
    config: FillInConfig, solution: FillInSolution, submission: FillInSubmission
) -> CheckResult:
    """One part per blank: a blank is correct when the chosen token matches the solution's. A
    wrong token gets the content's message for that blank and token, saying why it is wrong
    (FR-4.2), or a generic one. Only the chosen token's message is sent, never the answer."""
    parts: list[PartResult] = []
    for blank in config.blanks:
        have = submission.answers.get(blank)
        if have is None:
            parts.append(PartResult(ref=blank, correct=False, message=EMPTY_BLANK))
        elif have == solution.answers.get(blank):
            parts.append(PartResult(ref=blank, correct=True))
        else:
            message = solution.feedback.get(blank, {}).get(have, WRONG_CHOICE)
            parts.append(PartResult(ref=blank, correct=False, message=message))
    return _result(parts)


def check_trace(config: TraceConfig, submission: TraceSubmission) -> CheckResult:
    """One part per step: a step is correct when the student's visited vertex, queue, visited set
    and order all match the engine's step at that position (FR-6.6). The queue and the order are
    sequences, so their order counts; the visited set is a set, so it is compared regardless of the
    order the student wrote it in (a repeated vertex still makes it wrong). The traversal is the engine's,
    not a stored answer, so a trace is always graded against what the lessons teach (SE document
    decision "BFS computed server-side"); no `solution` is kept for this kind. A short answer leaves
    its missing steps wrong and a long one leaves its extra steps wrong, so both lower the score."""
    scenario = GraphScenarioOut(
        id=0,
        name="",
        directed=config.directed,
        vertices=config.vertices,
        edges=config.edges,
        start_vertex=config.start_vertex,
    )
    expected = run_bfs(scenario).steps  # raises InvalidGraph for a bad stored graph
    got = submission.rows
    parts: list[PartResult] = []
    for i in range(max(len(expected), len(got))):
        want = expected[i] if i < len(expected) else None
        have = got[i] if i < len(got) else None
        if want is None:
            parts.append(PartResult(ref=i, correct=False, message=EXTRA_TRACE_STEP))
        elif have is None:
            parts.append(PartResult(ref=i, correct=False, message=MISSING_TRACE_STEP))
        elif (
            have.visited_vertex == want.visited_vertex
            and have.queue == want.queue
            and sorted(have.visited) == sorted(want.visited)
            and have.order == want.order
        ):
            parts.append(PartResult(ref=i, correct=True))
        else:
            parts.append(PartResult(ref=i, correct=False, message=WRONG_TRACE_STEP))
    return _result(parts)


def check_multiple_choice(
    config: MultipleChoiceConfig,
    solution: MultipleChoiceSolution,
    submission: MultipleChoiceSubmission,
) -> CheckResult:
    """One part. A wrong option gets the content's message for that option, saying why it is
    wrong (FR-4.2). Nothing in the result names the correct option."""
    chosen = submission.selected
    if chosen not in {option.id for option in config.options}:
        message = UNKNOWN_OPTION
    elif chosen == solution.correct:
        message = RIGHT_OPTION
    else:
        message = solution.feedback.get(chosen, WRONG_OPTION)
    correct = chosen == solution.correct
    return CheckResult(
        correct=correct,
        score=1.0 if correct else 0.0,
        parts=[PartResult(ref=0, correct=correct, message=None if correct else message)],
        feedback=message,
    )


def check_matching(
    config: MatchingConfig, solution: MatchingSolution, submission: MatchingSubmission
) -> CheckResult:
    """One part per left item, in the config's order: correct when the student paired it with the
    solution's right item. A wrong pairing gets the content's message for that item (FR-4.2)."""
    parts: list[PartResult] = []
    for i, item in enumerate(config.left):
        have = submission.pairs.get(item.id)
        if have is None:
            parts.append(PartResult(ref=i, correct=False, message=NO_MATCH))
        elif have == solution.pairs.get(item.id):
            parts.append(PartResult(ref=i, correct=True))
        else:
            message = solution.feedback.get(item.id, WRONG_MATCH)
            parts.append(PartResult(ref=i, correct=False, message=message))
    return _result(parts)


def check_fix_the_bug(
    config: FixTheBugConfig, solution: FixTheBugSolution, submission: FixTheBugSubmission
) -> CheckResult:
    """One part per position of the fixed program, as in Parsons. The message says what went
    wrong there: a faulty line left in (with the content's reason it is faulty), the wrong
    correction, a correction where the original line was fine, a line in the wrong place, or an
    id that is neither a line nor a correction."""
    expected, got = solution.order, submission.order
    corrections = {line.id for line in config.corrections}
    lines = {line.id for line in config.lines}
    in_solution = set(expected)
    parts: list[PartResult] = []
    for i in range(max(len(expected), len(got))):
        want = expected[i] if i < len(expected) else None
        have = got[i] if i < len(got) else None
        if have == want:
            parts.append(PartResult(ref=i, correct=True))
            continue
        if want is None:
            message = EXTRA_LINE
        elif have is None:
            message = MISSING_LINE
        elif have in in_solution:
            message = OUT_OF_PLACE
        elif have in corrections:
            message = WRONG_FIX if want in corrections else FIX_NOT_NEEDED
        elif have not in lines:  # not a line or a correction at all: made up
            message = EXTRA_LINE
        else:  # an original line the fixed program does not use: a bug left in
            message = solution.feedback.get(have, BUG_LEFT_IN)
        parts.append(PartResult(ref=i, correct=False, message=message))
    return _result(parts)


def check_choose_tests(
    config: ChooseTestsConfig, solution: ChooseTestsSolution, submission: ChooseTestsSubmission
) -> CheckResult:
    """One part per test case, in the config's order: correct when the student's choice (selected
    or not) matches whether it exposes the bug. So selecting every test case, or none, cannot
    pass. A selected id that is not a test case adds a wrong part, as an unknown option does in
    multiple choice, so padding a right answer with a made-up id does not pass."""
    exposing, selected = set(solution.exposing), set(submission.selected)
    parts: list[PartResult] = []
    for i, test in enumerate(config.tests):
        if (test.id in selected) == (test.id in exposing):
            parts.append(PartResult(ref=i, correct=True))
        else:
            default = MISSED_TEST if test.id in exposing else NOT_EXPOSING
            message = solution.feedback.get(test.id, default)
            parts.append(PartResult(ref=i, correct=False, message=message))
    unknown = selected - {test.id for test in config.tests}
    parts.extend(
        PartResult(ref=len(config.tests) + i, correct=False, message=UNKNOWN_TEST)
        for i in range(len(unknown))
    )
    return _result(parts)


def check_activity(
    kind: str, config: dict[str, Any], solution: dict[str, Any], submission: dict[str, Any]
) -> CheckResult:
    """Parse the stored config and solution and the student's submission for `kind`, and grade."""
    if kind == "multiple_choice":
        return check_multiple_choice(
            MultipleChoiceConfig.model_validate(config),
            MultipleChoiceSolution.model_validate(solution),
            MultipleChoiceSubmission.model_validate(submission),
        )
    if kind == "parsons":
        return check_parsons(
            ParsonsConfig.model_validate(config),
            ParsonsSolution.model_validate(solution),
            ParsonsSubmission.model_validate(submission),
        )
    if kind == "fill_in":
        return check_fill_in(
            FillInConfig.model_validate(config),
            FillInSolution.model_validate(solution),
            FillInSubmission.model_validate(submission),
        )
    if kind == "matching":
        return check_matching(
            MatchingConfig.model_validate(config),
            MatchingSolution.model_validate(solution),
            MatchingSubmission.model_validate(submission),
        )
    if kind == "fix_the_bug":
        return check_fix_the_bug(
            FixTheBugConfig.model_validate(config),
            FixTheBugSolution.model_validate(solution),
            FixTheBugSubmission.model_validate(submission),
        )
    if kind == "choose_tests":
        return check_choose_tests(
            ChooseTestsConfig.model_validate(config),
            ChooseTestsSolution.model_validate(solution),
            ChooseTestsSubmission.model_validate(submission),
        )
    if kind == "trace":
        # No stored solution: the engine derives the answer from the graph in `config` (FR-6.6).
        return check_trace(
            TraceConfig.model_validate(config),
            TraceSubmission.model_validate(submission),
        )
    raise ValueError(f"unknown activity kind: {kind!r}")
