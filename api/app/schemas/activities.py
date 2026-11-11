"""Activity data: what the student is shown (`config`), the solution the server keeps, and what
the student submits, for each kind. Code activities run no student code (SE document FR-5,
NFR-S7); every kind is graded by comparing the submission with the solution in
`app/services/checking.py`.

A submission carries only line IDs and tokens the student chose from a given set, never free text,
so nothing a student sends here is ever executed or stored as free-form code.
"""

from typing import Annotated, Any, Literal

from pydantic import Field, ValidationInfo, field_validator, model_validator

from app.schemas.base import ApiModel
from app.schemas.graphs import VERTEX, GraphEdge

Vertex = Annotated[str, Field(pattern=VERTEX)]

CodeActivityKind = Literal["parsons", "fill_in", "fix_the_bug", "choose_tests"]
ActivityKind = Literal[
    "multiple_choice", "matching", "parsons", "fill_in", "trace", "fix_the_bug", "choose_tests"
]


# --- Multiple choice: pick one option (FR-4.1) ------------------------------------------------


class ChoiceOption(ApiModel):
    id: str = Field(min_length=1, max_length=50)
    label: str = Field(max_length=2_000)


class MultipleChoiceConfig(ApiModel):
    """Shown to the student: the question and its options, in the order to show them."""

    prompt: str = Field(max_length=5_000)
    options: list[ChoiceOption] = Field(min_length=2, max_length=10)


class Explained(ApiModel):
    """Server-only, on every kind with a stored solution: an optional explanation shown when the
    answer is right, saying why it is right (FR-4.2, ID document §7.4). Without one, a right
    answer gets the plain summary ("Correct.", "All correct.")."""

    explanation: str | None = Field(default=None, min_length=1, max_length=1_000)


class MultipleChoiceSolution(Explained):
    """Server-only: the correct option, and why each wrong one is wrong (FR-4.2), keyed by option
    id. A wrong option without a message gets a generic one."""

    correct: str
    feedback: dict[str, str] = Field(default_factory=dict)


class MultipleChoiceSubmission(ApiModel):
    selected: str = Field(max_length=50)


# --- Parsons: put shuffled lines in order ------------------------------------------------------


class ParsonsLine(ApiModel):
    id: int
    text: str = Field(max_length=5_000)


class ParsonsConfig(ApiModel):
    """Shown to the student: the lines to arrange, in any order. May include distractor lines
    that do not belong in the solution."""

    lines: list[ParsonsLine] = Field(min_length=1, max_length=100)


# One step of an accepted order: a line id, or a group of line ids that may go in any order among
# themselves (they still fill that stretch of the answer together), e.g. `[3, 4, 5]`.
ParsonsStep = int | Annotated[list[int], Field(max_length=100)]

# Validation context for content being stored (app/services/content.py): line ids must be real
# integers there, so `true` is not line 1 and `"3"` is not line 3. Grading parses a stored solution
# without it, so a solution stored before this rule still grades.
STRICT_IDS = {"strict_ids": True}


def _is_id(value: Any, strict: bool) -> bool:
    if strict:
        return isinstance(value, int) and not isinstance(value, bool)
    return not isinstance(value, (list, dict))  # pydantic's lax int decides the rest


def _check_steps(steps: Any, name: str, strict: bool) -> None:
    """A readable error for a malformed order, instead of pydantic's dump of the union."""
    if not isinstance(steps, list):
        raise ValueError(f"{name} must be a list of line ids")
    for step in steps:
        if isinstance(step, list):
            for line in step:
                if isinstance(line, list):
                    raise ValueError(f"{name}: a group holds line ids, not another group: {step}")
                if not _is_id(line, strict):
                    raise ValueError(f"{name}: {line!r} in the group {step} is not a line id")
        elif not _is_id(step, strict):
            raise ValueError(f"{name}: {step!r} is not a line id or a group of line ids")


def _strict(info: ValidationInfo) -> bool:
    return bool(info.context and info.context.get("strict_ids"))


class OrderedSolution(Explained):
    """Server-only: the accepted orders of line ids, for a kind graded by order (Parsons, fix the
    bug; FR-5.4, FR-5.5). Any line not used is a distractor (or, in fix the bug, a faulty line or
    an unused correction).

    `order` is one correct sequence. A step in it can be a list of line ids whose order doesn't
    matter, so `[1, 2, [3, 4, 5], 6]` accepts 1, 2, then 3, 4 and 5 in any of their six orders,
    then 6. `alternatives` lists more correct sequences in the same notation, for a line that can
    sit in a different place (not just swap with its neighbours); each must use the same lines as
    `order`. A plain list of ids, as before, is one order and nothing else. The checks that a
    solution makes sense (known ids, no line twice, no group of one, no alternative that `order`
    already accepts) are in app/services/content.py."""

    order: list[ParsonsStep] = Field(min_length=1, max_length=100)
    alternatives: list[Annotated[list[ParsonsStep], Field(min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=20
    )

    @field_validator("order", mode="before")
    @classmethod
    def _order_shape(cls, value: Any, info: ValidationInfo) -> Any:
        _check_steps(value, "order", _strict(info))
        return value

    @field_validator("alternatives", mode="before")
    @classmethod
    def _alternatives_shape(cls, value: Any, info: ValidationInfo) -> Any:
        if not isinstance(value, list):
            raise ValueError("alternatives must be a list of orders")
        for n, steps in enumerate(value, start=1):
            _check_steps(steps, f"alternative {n}", _strict(info))
        return value

    def accepted(self) -> list[list[ParsonsStep]]:
        """Every accepted order, `order` first."""
        return [self.order, *self.alternatives]

    def first_order(self) -> list[int]:
        """`order` as plain line ids, each group in the order written: one correct answer."""
        return flatten(self.order)


def flatten(steps: list[ParsonsStep]) -> list[int]:
    """The line ids of an accepted order, each group's ids in the order written."""
    return [i for step in steps for i in ([step] if isinstance(step, int) else step)]


class ParsonsSolution(OrderedSolution):
    """Server-only: the accepted orders of the lines (see OrderedSolution). Any line not used is
    a distractor."""


class ParsonsSubmission(ApiModel):
    order: list[int] = Field(max_length=100)


# --- Fill in the blank: choose a token for each blank ------------------------------------------


class FillInConfig(ApiModel):
    """Shown to the student: the code with numbered blanks and the tokens to choose from."""

    code: str = Field(max_length=20_000)
    blanks: list[int] = Field(min_length=1, max_length=100)
    options: list[str] = Field(min_length=1, max_length=200)


class FillInSolution(Explained):
    """Server-only: the correct token for each blank, keyed by blank id, and why a wrong token is
    wrong (FR-4.2): a message per blank and token, e.g. `{1: {"in": "Not quite. With in, …"}}`.
    A wrong token without a message gets a generic one."""

    answers: dict[int, str]
    feedback: dict[int, dict[str, str]] = Field(default_factory=dict)


class FillInSubmission(ApiModel):
    answers: dict[int, str] = Field(default_factory=dict)


# --- Matching: pair each item on the left with one on the right (FR-4.1; objectives 1 and 3) --


class MatchingItem(ApiModel):
    id: str = Field(min_length=1, max_length=50)
    label: str = Field(max_length=2_000)


class MatchingConfig(ApiModel):
    """Shown to the student: the items to match (`left`, e.g. terms or situations) and what to
    match them with (`right`, e.g. definitions or graph models). `right` may hold more choices
    than `left`, and a right item may fit more than one left item."""

    prompt: str = Field(max_length=5_000)
    left: list[MatchingItem] = Field(min_length=1, max_length=20)
    right: list[MatchingItem] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def unique_ids(self) -> "MatchingConfig":
        for side, items in (("left", self.left), ("right", self.right)):
            ids = [item.id for item in items]
            if len(ids) != len(set(ids)):
                raise ValueError(f"two {side} items share an id")
        return self


class MatchingSolution(Explained):
    """Server-only: the right item for each left item, and why a wrong pairing is wrong, keyed by
    left item id (FR-4.2)."""

    pairs: dict[str, str]
    feedback: dict[str, str] = Field(default_factory=dict)


class MatchingSubmission(ApiModel):
    """The right item the student chose for each left item; a left item may be left unmatched."""

    pairs: dict[str, str] = Field(default_factory=dict, max_length=20)


# --- Fix the bug: correct a faulty BFS (FR-5.5; objective 7) -----------------------------------


class FixTheBugConfig(ApiModel):
    """Shown to the student: the faulty program as lines, in its faulty order, and a set of
    correction lines. The student builds the fixed program: they replace each faulty line with
    a correction and move any line that is in the wrong place. Line and correction ids are one
    namespace, so the submission is simply the fixed program's ids in order."""

    prompt: str = Field(max_length=5_000)
    lines: list[ParsonsLine] = Field(min_length=1, max_length=100)
    corrections: list[ParsonsLine] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_ids(self) -> "FixTheBugConfig":
        ids = [line.id for line in self.lines] + [line.id for line in self.corrections]
        if len(ids) != len(set(ids)):
            raise ValueError("every line and correction needs its own id")
        return self


class FixTheBugSolution(OrderedSolution):
    """Server-only: the fixed program as line and correction ids, in its accepted orders (see
    OrderedSolution: groups and alternatives, FR-5.5), and why each faulty line is wrong, keyed by
    that line's id (FR-4.2)."""

    feedback: dict[int, str] = Field(default_factory=dict)


class FixTheBugSubmission(ApiModel):
    order: list[int] = Field(max_length=150)


# --- Choose tests: select the test cases that expose the bug (FR-5.5; objective 7) -------------


class TestCase(ApiModel):
    """A small graph, a start vertex and the order BFS should visit it in. The seed checks every
    `expected` against the BFS engine, so the correct BFS always passes every test case."""

    __test__ = False  # not a pytest test class, despite the name

    id: str = Field(min_length=1, max_length=50)
    directed: bool = False
    vertices: list[Vertex] = Field(min_length=1, max_length=20)
    edges: list[GraphEdge] = Field(default_factory=list, max_length=60)
    start_vertex: Vertex
    expected: list[Vertex] = Field(min_length=1, max_length=20)


class ChooseTestsConfig(ApiModel):
    """Shown to the student: the faulty BFS and four to six test cases (FR-5.5)."""

    prompt: str = Field(max_length=5_000)
    code: str = Field(max_length=20_000)
    tests: list[TestCase] = Field(min_length=2, max_length=8)

    @model_validator(mode="after")
    def unique_ids(self) -> "ChooseTestsConfig":
        ids = [test.id for test in self.tests]
        if len(ids) != len(set(ids)):
            raise ValueError("two test cases share an id")
        return self


class ChooseTestsSolution(Explained):
    """Server-only: the test cases the faulty version fails, and a message per test case for a
    wrong choice: why it does, or doesn't, expose the bug."""

    exposing: list[str] = Field(min_length=1)
    feedback: dict[str, str] = Field(default_factory=dict)


class ChooseTestsSubmission(ApiModel):
    selected: list[str] = Field(default_factory=list, max_length=8)


# --- Trace table: fill the BFS trace step by step (FR-4.1, FR-6.6) ----------------------------


class TraceConfig(ApiModel):
    """Shown to the student: the graph to trace, drawn the same way a scenario is (FR-6.1). The
    traversal itself is not here — the server derives it from this graph with the one BFS engine
    (FR-6.6), so the answer never reaches the browser."""

    directed: bool
    # Same label rule as a graph fixture, so a trace graph draws like any other scenario.
    vertices: list[Annotated[str, Field(pattern=VERTEX)]] = Field(min_length=1, max_length=50)
    edges: list[GraphEdge] = Field(max_length=200)
    start_vertex: str


# A vertex label as the student types it. Only the length is bounded (labels are at most 32
# characters, see VERTEX): a label that is not in the graph is a wrong answer, not a 422.
TracedVertex = Annotated[str, Field(max_length=32)]


class TraceRow(ApiModel):
    """One row of the student's trace table: the vertex visited (dequeued) at this step and the
    state after it — the queue, the visited set and the visit order (the columns in FR-4.1)."""

    visited_vertex: TracedVertex
    queue: list[TracedVertex] = Field(max_length=50)
    visited: list[TracedVertex] = Field(max_length=50)
    order: list[TracedVertex] = Field(max_length=50)


class TraceSubmission(ApiModel):
    rows: list[TraceRow] = Field(max_length=50)


# --- The result of checking a submission -------------------------------------------------------


class PartResult(ApiModel):
    """One graded part: a position in the ordering (Parsons, fix the bug), a blank id (fill-in),
    or the index of an item in the config (matching: a left item; choose tests: a test case)."""

    ref: int
    correct: bool
    message: str | None = None


class CheckResult(ApiModel):
    correct: bool
    score: float  # 0 to 1: the fraction of parts correct
    parts: list[PartResult]
    feedback: str


# --- Over the wire: what a GET returns and what a submission sends/gets back --------------------


class ActivityOut(ApiModel):
    """An activity as the browser sees it. There is deliberately no `solution` field: the answer
    stays on the server (SE document §8 "Answers never leave the server")."""

    id: int
    kind: str
    title: str
    visible: bool
    config: dict[str, Any]
    # This student has answered it correctly: no more hints are offered or given (#158). False
    # where the response isn't about one student's answers (a video's checkpoints). Always false
    # on a mastery check item, which doesn't say whether an answer was right (#144).
    solved: bool = False
    # A module 6 mastery item (#144): one answer only, no right or wrong shown (the mastery report
    # gives the results once every item is answered), and hints up to `MASTERY_HINT_LIMIT` only.
    mastery_check: bool = False
    # This student has answered this mastery check item, so it takes no more answers or hints.
    answered: bool = False


class AttemptIn(ApiModel):
    """A submission: only the student's choices (line ids, chosen tokens), never free-form code."""

    submitted: dict[str, Any]


class AttemptOut(ApiModel):
    """The graded result sent back. Carries per-part correctness and messages, never the solution.

    On a mastery check item (#144) the result is `withheld`: `correct` and `score` are null,
    `parts` is empty and `feedback` only says the answer was recorded. The mastery report shows
    the results once every module 6 item is answered."""

    id: int
    activity_id: int
    correct: bool | None
    score: float | None
    parts: list[PartResult]
    feedback: str
    withheld: bool = False
    # The highest hint level seen before this attempt; 3 or 4 means "with support" (FR-4.5).
    hint_level: int


class HintOut(ApiModel):
    """The hint just revealed. `next_counts_as_support` is true when the *next* hint would be level
    3 or 4: show the "this counts as met with support" warning before asking for it (ID doc §7.4)."""

    level: int
    body: str
    has_more: bool
    next_counts_as_support: bool
    # The mastery check's hint limit is reached and the activity has more hints it won't give
    # (#144): a student who needs them gets them on the objective's review path.
    limit_reached: bool = False
