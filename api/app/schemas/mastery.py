from typing import Literal

from app.schemas.base import ApiModel

ObjectiveState = Literal["not_attempted", "met_independently", "met_with_support", "not_yet"]


class ObjectiveReportOut(ApiModel):
    """One objective on the mastery report (FR-7.2, FR-7.3). `answered` of `total` is how many of
    its module 6 items the student has answered; the result stays `not_attempted` until all are."""

    id: int
    text: str
    criterion: str
    state: ObjectiveState
    answered: int
    total: int


class MasteryReportOut(ApiModel):
    """The student's own mastery report. `ready` (for the lecture) is true when every objective is
    met, with or without support (FR-7.4). Always shown, even when rewards are hidden (FR-9.5)."""

    ready: bool
    objectives: list[ObjectiveReportOut]
