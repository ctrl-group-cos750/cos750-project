"""Checks an activity's content before it is stored (SE document NFR-M5): the config and the
solution must have the kind's shape, and the solution must be one a student can actually reach.
The seed runs this on every fixture, so a broken content edit fails its PR in CI instead of
reaching a student.
"""

from typing import Any

from pydantic import BaseModel

from app.schemas.activities import (
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
    ParsonsConfig,
    ParsonsSolution,
    TraceConfig,
)
from app.schemas.base import ApiModel
from app.schemas.graphs import GraphScenarioOut
from app.services.bfs import InvalidGraph, run_bfs


class NoSolution(ApiModel):
    """A kind with no stored answer: the server derives it (trace is checked against the BFS
    engine, FR-6.6). Its fixture solution must be empty, `{}`."""


# The config and solution schemas for each kind (FR-4.1). Add a kind here when its checker lands.
SHAPES: dict[str, tuple[type[BaseModel], type[BaseModel]]] = {
    "multiple_choice": (MultipleChoiceConfig, MultipleChoiceSolution),
    "matching": (MatchingConfig, MatchingSolution),
    "parsons": (ParsonsConfig, ParsonsSolution),
    "fill_in": (FillInConfig, FillInSolution),
    "fix_the_bug": (FixTheBugConfig, FixTheBugSolution),
    "choose_tests": (ChooseTestsConfig, ChooseTestsSolution),
    "trace": (TraceConfig, NoSolution),
}


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
    known = lines | {line.id for line in config.corrections}
    if unknown := set(solution.order) - known:
        raise ValueError(f"the fixed program uses unknown line ids {sorted(unknown)}")
    if len(solution.order) != len(set(solution.order)):
        raise ValueError("the fixed program uses a line twice")
    if solution.order == [line.id for line in config.lines]:
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
    parsed_solution = solution_shape.model_validate(solution)
    match parsed_config, parsed_solution:
        case MultipleChoiceConfig(), MultipleChoiceSolution():
            _multiple_choice(parsed_config, parsed_solution)
        case MatchingConfig(), MatchingSolution():
            _matching(parsed_config, parsed_solution)
        case FixTheBugConfig(), FixTheBugSolution():
            _fix_the_bug(parsed_config, parsed_solution)
        case ChooseTestsConfig(), ChooseTestsSolution():
            _choose_tests(parsed_config, parsed_solution)
        case TraceConfig(), _:
            _trace(parsed_config)
        case _:
            pass  # Parsons and fill-in: the shapes are the whole check
