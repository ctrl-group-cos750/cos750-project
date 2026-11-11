"""Activity data: what the student is shown (`config`), the solution the server keeps, and what
the student submits, for each kind. Code activities run no student code (SE document FR-5,
NFR-S7); every kind is graded by comparing the submission with the solution in
`app/services/checking.py`.

A submission carries only line IDs and tokens the student chose from a given set, never free text,
so nothing a student sends here is ever executed or stored as free-form code. Every submission
shape bounds its sizes (#139): each string to the length of the longest thing it can name (an
option, item or test id, a token, a vertex label) and without control characters, each list and
dict to the most the config allows, and each line id to a Postgres integer. The stored submission
is what the student sent, so these bounds are what keeps it small.
"""

from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from app.schemas.base import ApiModel
from app.schemas.graphs import VERTEX, GraphEdge

Vertex = Annotated[str, Field(pattern=VERTEX)]

# No C0 control characters or DEL (NUL among them) in anything a student submits: no option, id,
# token or label contains one, and they would reach the evaluation export (FR-10).
NO_CONTROL = r"^[^\x00-\x1f\x7f]*$"
ID_LENGTH = 50  # option, matching item and test case ids (the configs' own bound)
TOKEN_LENGTH = 200  # a fill-in token (FillInConfig.options)

# A choice the student made, by id or by token: one of a fixed set, so short and printable.
ChosenId = Annotated[str, Field(max_length=ID_LENGTH, pattern=NO_CONTROL)]
ChosenToken = Annotated[str, Field(max_length=TOKEN_LENGTH, pattern=NO_CONTROL)]
# A line or blank id. Fixture ids are small; anything past a Postgres integer is never one.
SubmittedInt = Annotated[int, Field(ge=-(2**31), le=2**31 - 1)]

# The whole submission, in bytes of compact ASCII JSON. The largest right answer in the
# committed content is a trace table of about 660 (activity 618; tests/test_submission_limits.py
# checks the margin); this leaves room for far bigger content, and stops the one shape the
# per-field bounds still let grow (a trace table of a 50-vertex graph with 32-character labels,
# about 260 kB) from filling the attempts table.
MAX_SUBMISSION_BYTES = 16_384

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


class MultipleChoiceSolution(ApiModel):
    """Server-only: the correct option, and why each wrong one is wrong (FR-4.2), keyed by option
    id. A wrong option without a message gets a generic one."""

    correct: str
    feedback: dict[str, str] = Field(default_factory=dict)


class MultipleChoiceSubmission(ApiModel):
    selected: ChosenId


# --- Parsons: put shuffled lines in order ------------------------------------------------------


class ParsonsLine(ApiModel):
    id: int
    text: str = Field(max_length=5_000)


class ParsonsConfig(ApiModel):
    """Shown to the student: the lines to arrange, in any order. May include distractor lines
    that do not belong in the solution."""

    lines: list[ParsonsLine] = Field(min_length=1, max_length=100)


class ParsonsSolution(ApiModel):
    """Server-only: the correct sequence of line IDs. Any line not listed is a distractor."""

    order: list[int] = Field(min_length=1, max_length=100)


class ParsonsSubmission(ApiModel):
    order: list[SubmittedInt] = Field(max_length=100)


# --- Fill in the blank: choose a token for each blank ------------------------------------------


class FillInConfig(ApiModel):
    """Shown to the student: the code with numbered blanks and the tokens to choose from."""

    code: str = Field(max_length=20_000)
    blanks: list[int] = Field(min_length=1, max_length=100)
    options: list[Annotated[str, Field(max_length=TOKEN_LENGTH)]] = Field(
        min_length=1, max_length=200
    )


class FillInSolution(ApiModel):
    """Server-only: the correct token for each blank, keyed by blank id, and why a wrong token is
    wrong (FR-4.2): a message per blank and token, e.g. `{1: {"in": "Not quite. With in, …"}}`.
    A wrong token without a message gets a generic one."""

    answers: dict[int, str]
    feedback: dict[int, dict[str, str]] = Field(default_factory=dict)


class FillInSubmission(ApiModel):
    """The token chosen for each blank, keyed by blank id (at most FillInConfig's 100 blanks)."""

    answers: dict[SubmittedInt, ChosenToken] = Field(default_factory=dict, max_length=100)


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


class MatchingSolution(ApiModel):
    """Server-only: the right item for each left item, and why a wrong pairing is wrong, keyed by
    left item id (FR-4.2)."""

    pairs: dict[str, str]
    feedback: dict[str, str] = Field(default_factory=dict)


class MatchingSubmission(ApiModel):
    """The right item the student chose for each left item; a left item may be left unmatched."""

    pairs: dict[ChosenId, ChosenId] = Field(default_factory=dict, max_length=20)


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


class FixTheBugSolution(ApiModel):
    """Server-only: the fixed program as line and correction ids in order, and why each faulty
    line is wrong, keyed by that line's id (FR-4.2)."""

    order: list[int] = Field(min_length=1, max_length=100)
    feedback: dict[int, str] = Field(default_factory=dict)


class FixTheBugSubmission(ApiModel):
    order: list[SubmittedInt] = Field(max_length=150)


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


class ChooseTestsSolution(ApiModel):
    """Server-only: the test cases the faulty version fails, and a message per test case for a
    wrong choice: why it does, or doesn't, expose the bug."""

    exposing: list[str] = Field(min_length=1)
    feedback: dict[str, str] = Field(default_factory=dict)


class ChooseTestsSubmission(ApiModel):
    selected: list[ChosenId] = Field(default_factory=list, max_length=8)


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
TracedVertex = Annotated[str, Field(max_length=32, pattern=NO_CONTROL)]


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


class AttemptIn(ApiModel):
    """A submission: only the student's choices (line ids, chosen tokens), never free-form code.
    `submitted` is checked against the activity kind's shape above when it is graded."""

    submitted: dict[str, Any]


class AttemptOut(ApiModel):
    """The graded result sent back. Carries per-part correctness and messages, never the solution."""

    id: int
    activity_id: int
    correct: bool
    score: float
    parts: list[PartResult]
    feedback: str
    # The highest hint level seen before this attempt; 3 or 4 means "with support" (FR-4.5).
    hint_level: int


class HintOut(ApiModel):
    """The hint just revealed. `next_counts_as_support` is true when the *next* hint would be level
    3 or 4: show the "this counts as met with support" warning before asking for it (ID doc §7.4)."""

    level: int
    body: str
    has_more: bool
    next_counts_as_support: bool
