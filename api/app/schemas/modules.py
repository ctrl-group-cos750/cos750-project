"""Pydantic schemas for module-map and progress endpoints (SE document §9).

- ``ModuleOut``       — one module as the map shows it (id, status, counts, …)
- ``SegmentOut``      — one segment inside a module (kind-specific nullable fields)
- ``ModuleDetailOut`` — ``ModuleOut`` + ordered list of ``SegmentOut``
- ``PositionIn``      — request body for ``POST /api/modules/{moduleId}/position``

All schemas subclass ``ApiModel`` (camelCase JSON, from_attributes=True, extra=forbid).
"""

from typing import Literal

from app.schemas.base import ApiModel

# Allowed values for a student's progress through a module (FR-2.4 / FR-2.6).
ModuleStatus = Literal["locked", "open", "in_progress", "complete"]

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
    number: int
    slug: str
    title: str
    goals: str
    estimated_minutes: int
    # Computed at query time for the requesting student — not a DB column.
    status: ModuleStatus
    segment_count: int
    current_segment_position: int


class SegmentOut(ApiModel):
    """One segment of a module, in display order.

    Kind-specific nullable fields:
    - ``body``        — Markdown content, present only for ``text`` / ``worked_example``.
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


class ModuleDetailOut(ModuleOut):
    """A module with its full ordered segment list.

    Returned by ``GET /api/modules/{moduleId}``.  Extends ``ModuleOut`` so the
    frontend can use the same type for map cards and detail views.
    """

    segments: list[SegmentOut]


class PositionIn(ApiModel):
    """Request body for ``POST /api/modules/{moduleId}/position`` (FR-2.5).

    The client sends the zero-based position of the segment the student just
    reached; the server persists it in ``ModuleProgress.current_segment_position``.
    """

    segment_position: int
