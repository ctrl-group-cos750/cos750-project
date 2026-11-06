"""Code-activity data: what the student is shown (`config`), the solution the server keeps, and
what the student submits. Code activities run no student code (SE document FR-5, NFR-S7); each is
graded by comparing the submission with the solution in `app/services/checking.py`.

A submission carries only line IDs and tokens the student chose from a given set, never free text,
so nothing a student sends here is ever executed or stored as free-form code.
"""

from typing import Any, Literal

from pydantic import Field

from app.schemas.base import ApiModel
from app.schemas.graphs import GraphEdge

CodeActivityKind = Literal["parsons", "fill_in"]
ActivityKind = Literal["multiple_choice", "parsons", "fill_in", "trace"]


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
    selected: str = Field(max_length=50)


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
    order: list[int] = Field(max_length=100)


# --- Fill in the blank: choose a token for each blank ------------------------------------------


class FillInConfig(ApiModel):
    """Shown to the student: the code with numbered blanks and the tokens to choose from."""

    code: str = Field(max_length=20_000)
    blanks: list[int] = Field(min_length=1, max_length=100)
    options: list[str] = Field(min_length=1, max_length=200)


class FillInSolution(ApiModel):
    """Server-only: the correct token for each blank, keyed by blank id."""

    answers: dict[int, str]


class FillInSubmission(ApiModel):
    answers: dict[int, str] = Field(default_factory=dict)


# --- Trace table: fill the BFS trace step by step (FR-4.1, FR-6.6) ----------------------------


class TraceConfig(ApiModel):
    """Shown to the student: the graph to trace, drawn the same way a scenario is (FR-6.1). The
    traversal itself is not here — the server derives it from this graph with the one BFS engine
    (FR-6.6), so the answer never reaches the browser."""

    directed: bool
    vertices: list[str] = Field(min_length=1, max_length=50)
    edges: list[GraphEdge] = Field(max_length=200)
    start_vertex: str


class TraceRow(ApiModel):
    """One row of the student's trace table: the vertex visited (dequeued) at this step and the
    state after it — the queue, the visited set and the visit order (the columns in FR-4.1)."""

    visited_vertex: str
    queue: list[str] = Field(max_length=50)
    visited: list[str] = Field(max_length=50)
    order: list[str] = Field(max_length=50)


class TraceSubmission(ApiModel):
    rows: list[TraceRow] = Field(max_length=50)


# --- The result of checking a submission -------------------------------------------------------


class PartResult(ApiModel):
    """One graded part: a position in the ordering (Parsons) or a blank id (fill-in)."""

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
    """A submission: only the student's choices (line ids, chosen tokens), never free-form code."""

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
