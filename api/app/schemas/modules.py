"""Pydantic schemas for module-map and progress endpoints (SE document §9).

- ``ModuleOut``       — one module as the map shows it (id, status, counts, …)
- ``SegmentOut``      — one segment inside a module (kind-specific nullable fields)
- ``ModuleDetailOut`` — ``ModuleOut`` + ordered list of ``SegmentOut``
- ``PositionIn``      — request body for ``POST /api/modules/{moduleId}/position``

All schemas subclass ``ApiModel`` (camelCase JSON, from_attributes=True, extra=forbid).
"""

from typing import Literal

from pydantic import Field

from app.schemas.base import ApiModel

# Allowed values for a student's progress through a module (FR-2.1, FR-2.6, FR-8.2). Only the
# mastery check (module 6) is ever locked; `tested_out` is a module the student passed the quick
# check for instead of working through it (#214).
ModuleStatus = Literal["locked", "open", "in_progress", "complete", "tested_out"]

# A module's quick check for this student (FR-8.2, #214): `available` to take, or already taken
# and `passed` or `not_passed`. None for a module with no quick check (0 and 6), or one already
# complete before the student took it.
QuickCheckState = Literal["available", "passed", "not_passed"]

# The five kinds of segment a module can contain (matches Segment.kind in the DB).
SegmentKind = Literal["video", "text", "worked_example", "activity", "refresher"]


class ModuleOut(ApiModel):
    """A module as it appears on the module map.

    ``status`` is computed per-student at query time (never stored directly on the
    module); it is one of: locked | open | in_progress | complete.
    ``segment_count`` and ``current_segment_position`` let the map show a progress
    bar without loading the full segment list.
    """

    id: int
    # The module's number, 0 to 6. The same as `id` (a module's id is its number).
    number: int
    slug: str
    title: str
    # "By the end of this module you can …": one sentence per goal (FR-2.3).
    goals: list[str]
    estimated_minutes: int
    # Computed at query time for the requesting student — not a DB column.
    status: ModuleStatus
    segment_count: int
    # The furthest segment the student has reached, 0-based: where the module page resumes.
    current_segment_position: int
    # How many segments this student is shown: `segment_count` less the support segments they
    # don't need (FR-8.4). The map's minutes and the page's "Segment N of M" count these.
    shown_segment_count: int
    # How many of those shown segments come before `current_segment_position`.
    shown_segments_passed: int
    # The one module the map recommends next (FR-2.1, #214): the first in order the student hasn't
    # completed or tested out of. The warm-up (module 0) stops being recommended once any later
    # module is done. False on every module once all are done.
    recommended: bool = False
    # The module's quick check, for the "Already know this?" offer (FR-8.2, #214).
    quick_check: QuickCheckState | None = None


class CourseLengthOut(ApiModel):
    """How long the whole course takes, in minutes: the sum of the modules' estimates."""

    minutes: int


class SegmentOut(ApiModel):
    """One segment of a module, in display order.

    Kind-specific nullable fields:
    - ``body``        — Markdown content, for ``text`` / ``worked_example`` / ``refresher``.
    - ``video_id``    — FK to the video, present only for ``video`` segments.
    - ``activity_id`` — FK to the activity, present only for ``activity`` segments.

    ``body``, ``video_id``, and ``activity_id`` are mutually exclusive in practice;
    the schema keeps them separate and nullable so the frontend can branch on ``kind``.
    """

    id: int
    position: int
    kind: SegmentKind
    title: str
    # Populated only for text / worked_example segments.
    body: str | None = None
    # Populated only for video segments.
    video_id: int | None = None
    # Populated only for activity segments.
    activity_id: int | None = None
    # Support for this objective (FR-8.4): shown only to a student struggling with it here. The
    # page opens a run of support segments with a short, kind line saying why it is there.
    support_for: int | None = None
    # False for support this student doesn't need: it stays in the list, so positions never
    # shift, and is done, but the page skips it and doesn't count it.
    shown: bool = True
    # The student has done it, so they can move past it (FR-2.7): an activity answered at least
    # once, or every checkpoint of a video passed. Always true for every other kind.
    done: bool = True
    # The student has answered this segment's activity at least once, right or wrong. The page
    # opens a module at an activity the student passed *without* trying (one that had no screen
    # yet), never at one they tried and got wrong under an earlier rule (#165 review).
    attempted: bool = False
    # Done without a right answer (FR-2.7, #214): the student answered it wrongly
    # `ATTEMPTS_TO_MOVE_ON` times, or after its last hint, and may move on. The page says it is
    # marked to look at again. It is still not right: it earns nothing.
    look_again: bool = False
    # An optional bonus quest (FR-8.3): done whether or not it is answered, so it never holds
    # Next back; the page labels it optional.
    optional: bool = False


class RetrievalActivityOut(ApiModel):
    """A retrieval question the module opens with, before its segments (FR-2.4).

    The page loads the question itself from ``GET /api/activities/{id}``, so it is shown like any
    other activity, with feedback and hints. ``answered`` is true once the student has made an
    attempt at it: the page resumes at the first one still unanswered.
    """

    id: int
    title: str
    answered: bool


class ModuleDetailOut(ModuleOut):
    """A module with its full ordered segment list.

    Returned by ``GET /api/modules/{moduleId}``.  Extends ``ModuleOut`` so the
    frontend can use the same type for map cards and detail views.
    """

    segments: list[SegmentOut]
    # The retrieval questions, answered before the segments (FR-2.4). Not segments themselves.
    retrieval: list[RetrievalActivityOut]


class PositionIn(ApiModel):
    """Request body for ``POST /api/modules/{moduleId}/position`` (FR-2.5).

    The client sends the zero-based position of the segment the student just
    reached. The server keeps the furthest one, and refuses a position more than one past it,
    so a module can't be finished by jumping to its end.

    ``ge=0`` rejects negative values at the API boundary: a negative position stored in
    ``ModuleProgress.current_segment_position`` would cause ``segments[-1]`` (undefined
    in JavaScript) on resume, crashing the ModulePage render.
    """

    segment_position: int = Field(ge=0)


class QuickCheckOptionOut(ApiModel):
    id: str
    label: str


class QuickCheckQuestionOut(ApiModel):
    """One quick check question: multiple choice, no hints, no feedback until the end."""

    id: int
    title: str
    prompt: str
    options: list[QuickCheckOptionOut]


class QuickCheckItemResultOut(ApiModel):
    """How one question went, shown once every question is answered."""

    activity_id: int
    title: str
    prompt: str
    correct: bool
    # The option the student chose and the right one, as their labels.
    chosen: str
    answer: str
    explanation: str


class QuickCheckResultOut(ApiModel):
    """The quick check's result (FR-8.2, #214). `passed` with at most one wrong. `suggestion`:
    `move_on` after a pass, `start_with` an earlier module after a fail that points there (see
    app/services/quick_check.py), else `work_through` this module. `suggested_module` is the
    module named: the next one to do after a pass (None if there is none), the earlier one, or
    this one. `look_at` names what was missed: the titles of the questions answered wrongly."""

    passed: bool
    correct: int
    total: int
    suggestion: Literal["move_on", "start_with", "work_through"]
    suggested_module: int | None
    look_at: list[str]
    items: list[QuickCheckItemResultOut]


class QuickCheckOut(ApiModel):
    """`GET /api/modules/{moduleId}/quick-check`. `available` while the student may take it;
    `questions` then holds its questions. Once taken, `result` holds how it went."""

    module_id: int
    available: bool
    pass_mark: int
    questions: list[QuickCheckQuestionOut]
    result: QuickCheckResultOut | None = None


class QuickCheckAnswerIn(ApiModel):
    activity_id: int
    selected: str = Field(max_length=50)


class QuickCheckIn(ApiModel):
    """`POST /api/modules/{moduleId}/quick-check`: one answer for every question, sent together."""

    answers: list[QuickCheckAnswerIn] = Field(max_length=10)
