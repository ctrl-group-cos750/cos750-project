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
    ParsonsSubmission,
    PartResult,
)

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


def _result(parts: list[PartResult]) -> CheckResult:
    total = len(parts)
    right = sum(1 for part in parts if part.correct)
    correct = total > 0 and right == total
    feedback = "All correct." if correct else f"{right} of {total} correct."
    return CheckResult(
        correct=correct, score=right / total if total else 0.0, parts=parts, feedback=feedback
    )


def check_parsons(
    config: ParsonsConfig, solution: ParsonsSolution, submission: ParsonsSubmission
) -> CheckResult:
    """One part per position: a position is correct when the student's line id there matches the
    solution's. Extra lines (distractors placed, or a longer answer) and a short answer both fail
    the positions they affect, so they lower the score. `config` is accepted for a uniform checker
    signature; Parsons grading needs only the solution order."""
    expected, got = solution.order, submission.order
    in_solution = set(expected)  # a line id the answer should use somewhere
    parts: list[PartResult] = []
    for i in range(max(len(expected), len(got))):
        want = expected[i] if i < len(expected) else None
        have = got[i] if i < len(got) else None
        if have == want:
            parts.append(PartResult(ref=i, correct=True))
        elif want is None:
            parts.append(PartResult(ref=i, correct=False, message=EXTRA_LINE))
        elif have is None:
            parts.append(PartResult(ref=i, correct=False, message=MISSING_LINE))
        else:
            # A real line in the wrong place, or a distractor that does not belong at all.
            message = OUT_OF_PLACE if have in in_solution else EXTRA_LINE
            parts.append(PartResult(ref=i, correct=False, message=message))
    return _result(parts)


def check_fill_in(
    config: FillInConfig, solution: FillInSolution, submission: FillInSubmission
) -> CheckResult:
    """One part per blank: a blank is correct when the chosen token matches the solution's."""
    parts: list[PartResult] = []
    for blank in config.blanks:
        have = submission.answers.get(blank)
        if have is None:
            parts.append(PartResult(ref=blank, correct=False, message=EMPTY_BLANK))
        elif have == solution.answers.get(blank):
            parts.append(PartResult(ref=blank, correct=True))
        else:
            parts.append(PartResult(ref=blank, correct=False, message=WRONG_CHOICE))
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
    correction, a correction where the original line was fine, or a line in the wrong place."""
    expected, got = solution.order, submission.order
    corrections = {line.id for line in config.corrections}
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
        else:  # an original line the fixed program does not use: a bug left in
            message = solution.feedback.get(have, BUG_LEFT_IN)
        parts.append(PartResult(ref=i, correct=False, message=message))
    return _result(parts)


def check_choose_tests(
    config: ChooseTestsConfig, solution: ChooseTestsSolution, submission: ChooseTestsSubmission
) -> CheckResult:
    """One part per test case, in the config's order: correct when the student's choice (selected
    or not) matches whether it exposes the bug. So selecting every test case, or none, cannot
    pass."""
    exposing, selected = set(solution.exposing), set(submission.selected)
    parts: list[PartResult] = []
    for i, test in enumerate(config.tests):
        if (test.id in selected) == (test.id in exposing):
            parts.append(PartResult(ref=i, correct=True))
        else:
            default = MISSED_TEST if test.id in exposing else NOT_EXPOSING
            message = solution.feedback.get(test.id, default)
            parts.append(PartResult(ref=i, correct=False, message=message))
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
    raise ValueError(f"unknown activity kind: {kind!r}")
