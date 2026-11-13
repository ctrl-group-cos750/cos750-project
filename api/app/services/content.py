"""Checks an activity's content before it is stored (SE document NFR-M5): the config and the
solution must have the kind's shape, and the solution must be one a student can actually reach.
The seed runs this on every fixture, so a broken content edit fails its PR in CI instead of
reaching a student.
"""

from typing import Any

from pydantic import BaseModel

from app.schemas.activities import (
    STRICT_IDS,
    ChooseTestsConfig,
    ChooseTestsSolution,
    FillInConfig,
    FillInSolution,
    FixTheBugConfig,
    FixTheBugSolution,
    MatchingConfig,
    MatchingSolution,
    MultipleChoiceConfig,
    MultipleChoiceSolution,
    OrderedSolution,
    ParsonsConfig,
    ParsonsSolution,
    ParsonsStep,
    TraceConfig,
    TraceSolution,
    flatten,
)
from app.schemas.graphs import GraphScenarioOut
from app.services.bfs import InvalidGraph, run_bfs

# The config and solution schemas for each kind (FR-4.1). Add a kind here when its checker lands.
SHAPES: dict[str, tuple[type[BaseModel], type[BaseModel]]] = {
    "multiple_choice": (MultipleChoiceConfig, MultipleChoiceSolution),
    "matching": (MatchingConfig, MatchingSolution),
    "parsons": (ParsonsConfig, ParsonsSolution),
    "fill_in": (FillInConfig, FillInSolution),
    "fix_the_bug": (FixTheBugConfig, FixTheBugSolution),
    "choose_tests": (ChooseTestsConfig, ChooseTestsSolution),
    "trace": (TraceConfig, TraceSolution),
}


def _matches(steps: list[ParsonsStep], order: list[int]) -> bool:
    """Whether `steps` accepts `order` (plain line ids): each step fills the next stretch."""
    at = 0
    for step in steps:
        block = [step] if isinstance(step, int) else step
        if sorted(order[at : at + len(block)]) != sorted(block):
            return False
        at += len(block)
    return at == len(order)


def _covers(wide: list[ParsonsStep], narrow: list[ParsonsStep]) -> bool:
    """Whether every order `narrow` accepts is already accepted by `wide`: `wide` accepts its
    lines as written, and each of its groups sits inside one group of `wide`."""
    if not _matches(wide, flatten(narrow)):
        return False
    block_of = {
        line: n
        for n, step in enumerate(wide)
        for line in ([step] if isinstance(step, int) else step)
    }
    return all(
        len({block_of[line] for line in step}) == 1 for step in narrow if isinstance(step, list)
    )


def _orders(known: set[int], solution: OrderedSolution) -> None:
    """Every accepted order is one a student can build from the lines shown (FR-5.4, FR-5.5,
    NFR-M5), and each alternative accepts something the others don't."""
    used = set(solution.first_order())
    accepted = solution.accepted()
    for n, steps in enumerate(accepted):
        name = "the order" if n == 0 else f"alternative {n}"
        for step in steps:
            if isinstance(step, list) and len(step) < 2:
                # An empty group can't be placed; a group of one is just that line: write the id.
                raise ValueError(f"{name}: a group of lines needs at least two ids, not {step}")
        lines = flatten(steps)
        if unknown := sorted(set(lines) - known):
            raise ValueError(f"{name} uses unknown line ids {unknown}")
        if len(lines) != len(set(lines)):
            raise ValueError(f"{name} uses a line twice")
        if set(lines) != used:
            # Lines one order needs and another leaves out would be a distractor and an answer
            # line at once, so the feedback couldn't say which.
            raise ValueError(f"{name} must use the same lines as the order")
    for n, steps in enumerate(accepted[1:], start=1):
        if steps == solution.order:
            raise ValueError(f"alternative {n} is the order itself")
        for m, other in enumerate(accepted):
            if m != n and _covers(other, steps):
                where = "the order" if m == 0 else f"alternative {m}"
                raise ValueError(f"alternative {n} accepts nothing that {where} doesn't already")


def _parsons(config: ParsonsConfig, solution: ParsonsSolution) -> None:
    ids = [line.id for line in config.lines]
    if len(ids) != len(set(ids)):
        raise ValueError("two lines share an id, so a submission could not tell them apart")
    _orders(set(ids), solution)


def _multiple_choice(config: MultipleChoiceConfig, solution: MultipleChoiceSolution) -> None:
    ids = {option.id for option in config.options}
    if solution.correct not in ids:
        raise ValueError(f"correct option {solution.correct!r} is not one of the options")
    if unknown := set(solution.feedback) - ids:
        raise ValueError(f"feedback for unknown options {sorted(unknown)}")


def _matching(config: MatchingConfig, solution: MatchingSolution) -> None:
    left = {item.id for item in config.left}
    right = {item.id for item in config.right}
    if set(solution.pairs) != left:
        raise ValueError("the solution must pair every left item, and only those")
    if unknown := set(solution.pairs.values()) - right:
        raise ValueError(f"the solution pairs with unknown right items {sorted(unknown)}")
    if unknown := set(solution.feedback) - left:
        raise ValueError(f"feedback for unknown left items {sorted(unknown)}")


def _fix_the_bug(config: FixTheBugConfig, solution: FixTheBugSolution) -> None:
    lines = {line.id for line in config.lines}
    _orders(lines | {line.id for line in config.corrections}, solution)
    if any(_matches(steps, [line.id for line in config.lines]) for steps in solution.accepted()):
        raise ValueError("the fixed program is the faulty one: there is nothing to fix")
    if unknown := set(solution.feedback) - lines:
        raise ValueError(f"feedback for ids that are not faulty-program lines {sorted(unknown)}")


def _choose_tests(config: ChooseTestsConfig, solution: ChooseTestsSolution) -> None:
    ids = {test.id for test in config.tests}
    if unknown := set(solution.exposing) - ids:
        raise ValueError(f"exposing names unknown test cases {sorted(unknown)}")
    if set(solution.exposing) == ids:
        raise ValueError("every test case exposes the bug, so choosing all of them would pass")
    if unknown := set(solution.feedback) - ids:
        raise ValueError(f"feedback for unknown test cases {sorted(unknown)}")
    for test in config.tests:
        # The correct BFS must pass every test case, or "fails the faulty version and passes the
        # correct one" (ID document Table 1, objective 7) means nothing. Check it with the engine.
        scenario = GraphScenarioOut(
            id=0,
            name=test.id,
            directed=test.directed,
            vertices=test.vertices,
            edges=test.edges,
            start_vertex=test.start_vertex,
        )
        try:
            order = run_bfs(scenario).order
        except InvalidGraph as exc:
            raise ValueError(f"test case {test.id!r}: {exc}") from exc
        if order != test.expected:
            raise ValueError(
                f"test case {test.id!r}: expected {test.expected}, but BFS visits {order}"
            )


def _fill_in(config: FillInConfig, solution: FillInSolution) -> None:
    blanks, options = set(config.blanks), set(config.options)
    # Every blank has an answer a student can choose, and nothing else does (NFR-M5).
    if missing := sorted(blanks - set(solution.answers)):
        raise ValueError(f"no answer for blanks {missing}")
    if unknown := sorted(set(solution.answers) - blanks):
        raise ValueError(f"answers for blanks that don't exist {unknown}")
    for blank, token in sorted(solution.answers.items()):
        if token not in options:
            raise ValueError(f"blank {blank}: the answer {token!r} is not one of the options")
    for blank, messages in sorted(solution.feedback.items()):
        if blank not in blanks:
            raise ValueError(f"feedback for blank {blank}, which doesn't exist")
        if not_options := sorted(set(messages) - options):
            raise ValueError(
                f"blank {blank}: feedback for tokens that aren't options {not_options}"
            )
        if solution.answers[blank] in messages:
            # The right token never gets a wrong-answer message, so this one could never show.
            raise ValueError(f"blank {blank}: feedback for the correct token")


def _trace(config: TraceConfig) -> None:
    # The traversal is the engine's, so a graph it refuses would only fail when a student opens
    # it; catch it at load, as the seed does for graph scenarios (FR-6.6).
    try:
        run_bfs(GraphScenarioOut(id=0, name="", **config.model_dump()))
    except InvalidGraph as exc:
        raise ValueError(str(exc)) from exc


def validate_activity(kind: str, config: dict[str, Any], solution: dict[str, Any]) -> None:
    """Raises ValueError (pydantic's ValidationError is one) when the content can't work."""
    if kind not in SHAPES:
        raise ValueError(f"unknown activity kind: {kind!r}")
    config_shape, solution_shape = SHAPES[kind]
    parsed_config = config_shape.model_validate(config)
    parsed_solution = solution_shape.model_validate(solution, context=STRICT_IDS)
    match parsed_config, parsed_solution:
        case MultipleChoiceConfig(), MultipleChoiceSolution():
            _multiple_choice(parsed_config, parsed_solution)
        case MatchingConfig(), MatchingSolution():
            _matching(parsed_config, parsed_solution)
        case FixTheBugConfig(), FixTheBugSolution():
            _fix_the_bug(parsed_config, parsed_solution)
        case ChooseTestsConfig(), ChooseTestsSolution():
            _choose_tests(parsed_config, parsed_solution)
        case FillInConfig(), FillInSolution():
            _fill_in(parsed_config, parsed_solution)
        case ParsonsConfig(), ParsonsSolution():
            _parsons(parsed_config, parsed_solution)
        case TraceConfig(), _:
            _trace(parsed_config)
