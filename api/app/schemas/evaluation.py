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
    """How far students got through one video: who started it (or answered one of its
    checkpoints), who passed each checkpoint and who watched to the end. A drop between two steps
    is where students stopped."""

    id: int
    title: str
    students: int  # started it, or answered one of its checkpoints
    finished: int  # watched it to the end
    checkpoints: list[CheckpointInsight]


class Insights(ApiModel):
    students: int  # real students (not staff or demo) who did anything: answered, asked for a
    # hint, or anything in the event log, such as starting a video
    attempts: int
    hints_viewed: int
    activities: list[ActivityInsight]
    videos: list[VideoInsight]


class ObjectiveReadiness(ApiModel):
    """How the class stands on one objective, among students who have answered the mastery check."""

    id: int
    text: str
    met_independently: int
    met_with_support: int
    not_yet: int


class CommonWrongAnswer(ApiModel):
    """The wrong option chosen most often, at first answer, on one multiple-choice assessed item:
    the misconception to address in the lecture."""

    activity_id: int
    title: str
    objective_id: int | None
    answered: int  # students who answered it
    wrong: int  # students whose first answer was wrong
    option: str  # the wrong option chosen most
    chosen_by: int
    why_wrong: str | None  # the content's feedback for that option


class Readiness(ApiModel):
    """Before the lecture (Just-in-Time Teaching, Novak et al. 1999): who is ready, how the class
    stands on each objective, and the wrong answers the lecture should address first."""

    students: int  # real students who have answered at least one mastery item
    ready: int  # of them, how many met every objective
    objectives: list[ObjectiveReadiness]
    common_wrong_answers: list[CommonWrongAnswer]
