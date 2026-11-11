"""What the staff content editor sends and gets back (app/routers/staff_content.py).

The fields are the content fixtures' (app/seed), in camelCase. Every save is checked twice: the
item on its own, by the same models the fixtures use, and then all the content together, by the
same cross-checks CI runs on the fixtures (`check_content`). Like the video editor's schemas,
these carry solutions: only staff routes use them.
"""

from typing import Any

from pydantic import Field

from app.schemas.activities import ActivityKind
from app.schemas.base import ApiModel
from app.schemas.content import Purpose, SegmentKind
from app.schemas.graphs import GraphEdge
from app.schemas.staff import StaffHint


class EditorProvenance(ApiModel):
    """Where an item's current version comes from. `edited` means staff changed it in the portal,
    so the seed leaves it alone; `inRepository` means the fixtures have a version of it, which
    "Use the repository's version" brings back."""

    edited: bool
    in_repository: bool


class EditorObjectiveIn(ApiModel):
    text: str
    bloom_level: str
    criterion: str
    # Exactly one: at least this fraction of the module 6 parts right, or at most this many wrong.
    pass_fraction: float | None = None
    max_wrong: int | None = None


class EditorObjectiveOut(EditorObjectiveIn, EditorProvenance):
    id: int


class EditorSegmentIn(ApiModel):
    """One step of a module or review path. Leave `id` out for a new one. A `video` segment may
    name the video that plays it (`videoId`); the video is made on the Videos page."""

    id: int | None = None
    kind: SegmentKind
    title: str
    body: str = ""
    activity_id: int | None = None
    skip_check_activity_id: int | None = None
    refresher_for: str | None = None
    # The objective this module segment is support for (FR-8.4): shown only to a student
    # struggling with it in this module. Not in module 6 or on a review path.
    support_for: int | None = None
    video_id: int | None = None


class EditorSegmentOut(EditorSegmentIn):
    id: int


class EditorModuleIn(ApiModel):
    slug: str
    title: str
    goals: list[str]
    estimated_minutes: int
    segments: list[EditorSegmentIn] = Field(default_factory=list)


class EditorModuleOut(EditorProvenance):
    id: int
    slug: str
    title: str
    goals: list[str]
    estimated_minutes: int
    segments: list[EditorSegmentOut]
    # Its list of segments was changed in the portal (separately from its title and goals).
    segments_edited: bool


class EditorModuleSummary(EditorProvenance):
    id: int
    slug: str
    title: str
    segment_count: int
    segments_edited: bool


class EditorReviewPathIn(ApiModel):
    segments: list[EditorSegmentIn]


class EditorReviewPathOut(ApiModel):
    objective_id: int
    segments: list[EditorSegmentOut]
    edited: bool
    in_repository: bool


class EditorReviewPathSummary(ApiModel):
    objective_id: int
    segment_count: int
    edited: bool
    in_repository: bool


class EditorActivityIn(ApiModel):
    """`config` and `solution` have the kind's shape (app/schemas/activities.py), exactly as in a
    fixture."""

    kind: ActivityKind
    title: str
    visible: bool = True
    module_id: int | None = None
    objective_id: int | None = None
    purpose: Purpose = "practice"
    config: dict[str, Any]
    solution: dict[str, Any]
    hints: list[StaffHint] = Field(default_factory=list, max_length=4)


class EditorActivityOut(EditorActivityIn, EditorProvenance):
    id: int
    # Students have answered it or asked for a hint: deleting it only takes it out of use.
    in_use: bool
    # The segments that show it, as "module 3: Trace the queue".
    shown_in: list[str]


class EditorActivitySummary(EditorProvenance):
    id: int
    kind: ActivityKind
    title: str
    module_id: int | None
    objective_id: int | None
    purpose: Purpose


class EditorGraphIn(ApiModel):
    name: str
    directed: bool = False
    vertices: list[str]
    edges: list[GraphEdge] = Field(default_factory=list)
    start_vertex: str


class EditorGraphOut(EditorGraphIn, EditorProvenance):
    id: int


class EditorGraphSummary(EditorProvenance):
    id: int
    name: str


class EditorVideoChoice(ApiModel):
    """A video a `video` segment can play, and the segment that plays it now, if any."""

    id: int
    title: str
    segment_id: int | None


class EditorContentOverview(ApiModel):
    objectives: list[EditorObjectiveOut]
    modules: list[EditorModuleSummary]
    review_paths: list[EditorReviewPathSummary]
    # Every activity the content editor can edit. The video editor's checkpoint questions are
    # edited there, so they are left out.
    activities: list[EditorActivitySummary]
    graphs: list[EditorGraphSummary]
    videos: list[EditorVideoChoice]


class EditorDeleteResult(ApiModel):
    """`deleted`: the row is gone. Otherwise it was only taken out of use (students' answers to
    it are kept for the evaluation, FR-10)."""

    deleted: bool
