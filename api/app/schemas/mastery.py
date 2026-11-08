from typing import Literal

from app.schemas.base import ApiModel
from app.schemas.content import SegmentKind

ObjectiveState = Literal["not_attempted", "met_independently", "met_with_support", "not_yet"]


class ReviewProgressOut(ApiModel):
    """How far the student is through an open review path's fresh items (FR-7.5). Once all are
    answered they decide the objective's result, so `answered == total` means the path is done."""

    answered: int
    total: int


class ObjectiveReportOut(ApiModel):
    """One objective on the mastery report (FR-7.2, FR-7.3). `answered` of `total` is how many of
    its module 6 items the student has answered; the result stays `not_attempted` until all are.
    `review` is there once module 6 marks it "not yet", which opens its review path."""

    id: int
    text: str
    criterion: str
    state: ObjectiveState
    answered: int
    total: int
    review: ReviewProgressOut | None


class MasteryReportOut(ApiModel):
    """The student's own mastery report. `ready` (for the lecture) is true when every objective is
    met, with or without support (FR-7.4). Always shown, even when rewards are hidden (FR-9.5)."""

    ready: bool
    objectives: list[ObjectiveReportOut]


class ReviewStepOut(ApiModel):
    """One step of a review path, in order. An activity step names its activity and its purpose:
    `review` is practice with the full hint ladder, `mastery` a fresh item that decides the
    result. `answered` is whether the student has submitted an answer to it."""

    id: int
    kind: SegmentKind
    title: str
    body: str  # Markdown, for a text or worked example step
    activity_id: int | None
    purpose: Literal["review", "mastery"] | None
    answered: bool


class ReviewPathOut(ApiModel):
    """An objective's review path for the logged-in student (FR-7.5, ID document §7.6)."""

    objective_id: int
    objective_text: str
    criterion: str
    state: ObjectiveState  # the objective's result now
    progress: ReviewProgressOut  # the fresh items
    steps: list[ReviewStepOut]
