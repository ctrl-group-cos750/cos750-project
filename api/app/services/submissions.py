"""Whether a submission is an answer to this activity at all, before it is graded (#139).

A submission in the right shape can still name ids the activity doesn't have (a line, blank,
token, option, test case or vertex that isn't in its config). Grading one would store it as a
real attempt, and on a mastery item only the first attempt counts (FR-7.2), so a stray request
would spend the student's one try. The activity routes refuse it with 422 instead, before
anything is recorded. A blank submission (no option, pairs, lines, blanks or rows) is refused the
same way by `record_attempt` (`checking.is_blank`, `BlankAnswer`, #143), so it isn't checked here.

A select the student touched and then reset sends "" for that pair or blank: `clean` drops those
first, so they count as left unanswered, exactly like a select never touched, and the rest is
graded.

A choice that is in the config but wrong (a wrong option, a line out of place, a vertex visited
too early) is an answer, and is graded as before.
"""

from typing import Any, Literal

from app.schemas.activities import (
    ChooseTestsConfig,
    ChooseTestsSubmission,
    FillInConfig,
    FillInSubmission,
    FixTheBugConfig,
    FixTheBugSubmission,
    MatchingConfig,
    MatchingSubmission,
    MultipleChoiceConfig,
    MultipleChoiceSubmission,
    ParsonsConfig,
    ParsonsSubmission,
    TraceConfig,
    TraceSubmission,
)

Problem = Literal["foreign"]


def _foreign(chosen: set[Any], offered: set[Any]) -> bool:
    return not chosen <= offered


def clean(kind: str, submitted: dict[str, Any]) -> dict[str, Any]:
    """`submitted` with every "" choice in a matching pair or fill-in blank left out: a select the
    student reset is a choice not made. Anything else is returned unchanged."""
    field = {"matching": "pairs", "fill_in": "answers"}.get(kind)
    if field is None:
        return submitted
    chosen = submitted.get(field)
    if not isinstance(chosen, dict):
        return submitted
    return {**submitted, field: {k: v for k, v in chosen.items() if v != ""}}


def submission_problem(
    kind: str, config: dict[str, Any], submitted: dict[str, Any]
) -> Problem | None:
    """None if `submitted` names only what this activity offers (or nothing at all: that is left to
    `record_attempt`'s blank check); "foreign" if it names something the config doesn't offer. Raises pydantic's ValidationError if it
    isn't in the kind's shape, like the checker. A kind this doesn't know is left to the checker."""
    if kind == "multiple_choice":
        mc = MultipleChoiceSubmission.model_validate(submitted)
        if not mc.selected.strip():
            return None  # blank: record_attempt refuses it (BlankAnswer)
        options = {o.id for o in MultipleChoiceConfig.model_validate(config).options}
        return "foreign" if mc.selected not in options else None
    if kind == "matching":
        matching = MatchingSubmission.model_validate(submitted)
        cfg = MatchingConfig.model_validate(config)
        if not matching.pairs:
            return None  # blank: record_attempt refuses it (BlankAnswer)
        left, right = {i.id for i in cfg.left}, {i.id for i in cfg.right}
        foreign = _foreign(set(matching.pairs), left) or _foreign(
            set(matching.pairs.values()), right
        )
        return "foreign" if foreign else None
    if kind == "parsons":
        parsons = ParsonsSubmission.model_validate(submitted)
        if not parsons.order:
            return None  # blank: record_attempt refuses it (BlankAnswer)
        lines = {line.id for line in ParsonsConfig.model_validate(config).lines}
        return "foreign" if _foreign(set(parsons.order), lines) else None
    if kind == "fix_the_bug":
        fix = FixTheBugSubmission.model_validate(submitted)
        if not fix.order:
            return None  # blank: record_attempt refuses it (BlankAnswer)
        cfg_fix = FixTheBugConfig.model_validate(config)
        ids = {line.id for line in cfg_fix.lines} | {line.id for line in cfg_fix.corrections}
        return "foreign" if _foreign(set(fix.order), ids) else None
    if kind == "fill_in":
        fill = FillInSubmission.model_validate(submitted)
        if not fill.answers:
            return None  # blank: record_attempt refuses it (BlankAnswer)
        cfg_fill = FillInConfig.model_validate(config)
        foreign = _foreign(set(fill.answers), set(cfg_fill.blanks)) or _foreign(
            set(fill.answers.values()), set(cfg_fill.options)
        )
        return "foreign" if foreign else None
    if kind == "choose_tests":
        chosen = ChooseTestsSubmission.model_validate(submitted)
        if not chosen.selected:
            return None  # blank: record_attempt refuses it (BlankAnswer)
        tests = {t.id for t in ChooseTestsConfig.model_validate(config).tests}
        return "foreign" if _foreign(set(chosen.selected), tests) else None
    if kind == "trace":
        trace = TraceSubmission.model_validate(submitted)
        if not trace.rows:
            return None  # blank: record_attempt refuses it (BlankAnswer)
        vertices = set(TraceConfig.model_validate(config).vertices)
        named = {
            label
            for row in trace.rows
            for label in (row.visited_vertex, *row.queue, *row.visited, *row.order)
        }
        return "foreign" if _foreign(named, vertices) else None
    return None
