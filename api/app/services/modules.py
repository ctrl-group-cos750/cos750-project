"""The module map and each student's progress through the modules (SE document §9, FR-2).

The modules and their segments are content (app/models/content.py, loaded from the fixtures);
`ModuleProgress` is the student's part. Functions take a session and the student's id, flush
and never commit: the router commits.

Unlocking (FR-2.1): the first module (by `position`) is always open. Any other module opens when
the one before it is complete, and stays as it is once the student has started it.

Progress (FR-2.5, FR-2.6): the student moves through a module one segment at a time. The
furthest segment reached is kept, so stepping back to reread never loses progress, and reaching
the last segment completes the module for good.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Module, ModuleProgress, Segment, Video
from app.schemas.modules import (
    ModuleDetailOut,
    ModuleOut,
    ModuleStatus,
    RetrievalActivityOut,
    SegmentOut,
)


class ModuleNotFound(ValueError):
    """No module has this id."""


class ModuleLocked(ValueError):
    """The module before this one isn't complete yet."""


class PositionTooFar(ValueError):
    """The position is more than one segment past the furthest the student has reached."""


class RetrievalIncomplete(ValueError):
    """The student has not answered every retrieval item before starting the module."""


def _modules(session: Session) -> Sequence[Module]:
    return session.scalars(select(Module).order_by(Module.position)).all()


def _progress(session: Session, user_id: int) -> dict[int, ModuleProgress]:
    rows = session.scalars(select(ModuleProgress).where(ModuleProgress.user_id == user_id))
    return {row.module_id: row for row in rows}


def _segments(session: Session, module_id: int) -> Sequence[Segment]:
    return session.scalars(
        select(Segment).where(Segment.module_id == module_id).order_by(Segment.position)
    ).all()


def _statuses(
    modules: Sequence[Module], progress: dict[int, ModuleProgress]
) -> dict[int, ModuleStatus]:
    """Each module's status for one student, in map order (FR-2.1)."""
    statuses: dict[int, ModuleStatus] = {}
    previous_complete = True  # nothing comes before the first module
    for module in modules:
        row = progress.get(module.id)
        if row is not None and row.status == "complete":
            status: ModuleStatus = "complete"
        elif row is not None:
            status = "in_progress"
        else:
            status = "open" if previous_complete else "locked"
        statuses[module.id] = status
        previous_complete = status == "complete"
    return statuses


def _status(session: Session, user_id: int, module_id: int) -> ModuleStatus:
    modules = _modules(session)
    if not any(module.id == module_id for module in modules):
        raise ModuleNotFound(module_id)
    return _statuses(modules, _progress(session, user_id))[module_id]


def _summary(
    module: Module, status: ModuleStatus, segment_count: int, row: ModuleProgress | None
) -> ModuleOut:
    return ModuleOut(
        id=module.id,
        number=module.id,
        slug=module.slug,
        title=module.title,
        goals=module.goals,
        estimated_minutes=module.estimated_minutes,
        status=status,
        segment_count=segment_count,
        current_segment_position=row.current_segment_position if row else 0,
    )


def get_modules_for_user(session: Session, user_id: int) -> list[ModuleOut]:
    """Every module in map order, with this student's status and progress."""
    modules = _modules(session)
    progress = _progress(session, user_id)
    statuses = _statuses(modules, progress)
    counts: dict[int, int] = {}
    for module_id in session.scalars(
        select(Segment.module_id).where(Segment.module_id.isnot(None))
    ):
        if module_id is not None:
            counts[module_id] = counts.get(module_id, 0) + 1
    return [
        _summary(module, statuses[module.id], counts.get(module.id, 0), progress.get(module.id))
        for module in modules
    ]


def get_module_detail(session: Session, user_id: int, module_id: int) -> ModuleDetailOut:
    """One module with its segments in order. Raises `ModuleNotFound` or `ModuleLocked`."""
    status = _status(session, user_id, module_id)
    if status == "locked":
        raise ModuleLocked(module_id)
    module = session.get_one(Module, module_id)
    row = session.scalar(
        select(ModuleProgress).where(
            ModuleProgress.user_id == user_id, ModuleProgress.module_id == module_id
        )
    )
    segments = _segments(session, module_id)
    retrieval = session.scalars(
        select(Activity)
        .where(Activity.module_id == module_id, Activity.purpose == "retrieval")
        .order_by(Activity.id)
    ).all()
    # A video segment's video points at it (Video.segment_id): videos are made in the app.
    videos = {
        video.segment_id: video.id
        for video in session.scalars(
            select(Video).where(Video.segment_id.in_([segment.id for segment in segments]))
        )
    }
    # TODO (FR-8.1): leave out the refreshers module 0's diagnostic has ruled out, once the
    # diagnostic records its result. Until then every refresher is shown.
    return ModuleDetailOut(
        **_summary(module, status, len(segments), row).model_dump(),
        segments=[
            SegmentOut(
                id=segment.id,
                position=index,
                kind=segment.kind,  # type: ignore[arg-type]
                title=segment.title,
                body=segment.body or None,
                video_id=videos.get(segment.id),
                activity_id=segment.activity_id,
            )
            for index, segment in enumerate(segments)
        ],
        retrieval=[
            RetrievalActivityOut(
                id=activity.id,
                title=activity.title,
                prompt=activity.config["prompt"],
                options=activity.config["options"],
            )
            for activity in retrieval
        ],
    )


def save_position(
    session: Session, user_id: int, module_id: int, segment_position: int
) -> ModuleProgress:
    """Record that the student reached `segment_position` (0-based) in this module.

    The furthest position reached is kept: stepping back is allowed and changes nothing. Moving
    more than one segment past the furthest raises `PositionTooFar`. Reaching the last segment
    completes the module, and a complete module stays complete (FR-2.6). Raises `ModuleNotFound`
    or `ModuleLocked` like `get_module_detail`.
    """
    status = _status(session, user_id, module_id)
    if status == "locked":
        raise ModuleLocked(module_id)
    retrieval_ids = session.scalars(
        select(Activity.id).where(Activity.module_id == module_id, Activity.purpose == "retrieval")
    ).all()
    answered_ids = set(
        session.scalars(
            select(Attempt.activity_id).where(
                Attempt.user_id == user_id, Attempt.activity_id.in_(retrieval_ids)
            )
        )
    )
    if retrieval_ids and not set(retrieval_ids) <= answered_ids:
        raise RetrievalIncomplete(module_id)
    last = len(_segments(session, module_id)) - 1
    if last < 0:
        raise PositionTooFar(module_id)  # nothing to move through yet
    row = session.scalar(
        select(ModuleProgress)
        .where(ModuleProgress.user_id == user_id, ModuleProgress.module_id == module_id)
        .with_for_update()
    )
    reached = row.current_segment_position if row else 0
    if segment_position > min(reached + 1, last):
        raise PositionTooFar(module_id)
    if row is None:
        row = ModuleProgress(user_id=user_id, module_id=module_id, status="in_progress")
        session.add(row)
    row.current_segment_position = max(reached, segment_position)
    if row.current_segment_position == last and row.status != "complete":
        row.status = "complete"
        row.completed_at = datetime.now(tz=UTC)
    session.flush()
    return row
