"""What the staff portal's "Pilot insights" page gets back (app/routers/staff_evaluation.py).
Counts only: no names, emails or answers."""

from app.schemas.base import ApiModel


class ActivityInsight(ApiModel):
    """How students got on with one activity, as ID document §8.4 analyses it."""

    id: int
    title: str
    kind: str
    students: int  # who answered it at least once
    attempts: int
    wrong_attempts: int
    students_passed: int  # who got it right at least once
    students_with_support: int  # who were shown hint level 3 or 4


class CheckpointInsight(ApiModel):
    id: int
    at_seconds: float
    activity_title: str
    students_passed: int


class VideoInsight(ApiModel):
    """How far students got through one video: who answered any of its checkpoints, and who passed
    each one. A drop between two checkpoints is where students stopped."""

    id: int
    title: str
    students: int
    checkpoints: list[CheckpointInsight]


class Insights(ApiModel):
    students: int  # student accounts (not staff) that have answered or asked for a hint
    attempts: int
    hints_viewed: int
    activities: list[ActivityInsight]
    videos: list[VideoInsight]
