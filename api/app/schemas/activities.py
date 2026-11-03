"""Code-activity data: what the student is shown (`config`), the solution the server keeps, and
what the student submits. Code activities run no student code (SE document FR-5, NFR-S7); each is
graded by comparing the submission with the solution in `app/services/checking.py`.

A submission carries only line IDs and tokens the student chose from a given set, never free text,
so nothing a student sends here is ever executed or stored as free-form code.
"""

from typing import Literal

from pydantic import Field

from app.schemas.base import ApiModel

CodeActivityKind = Literal["parsons", "fill_in"]


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
