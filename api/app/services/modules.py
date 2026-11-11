"""The module map and each student's progress through the modules (SE document §9, FR-2).

The modules and their segments are content (app/models/content.py, loaded from the fixtures);
`ModuleProgress` is the student's part. Functions take a session and the student's id, flush
and never commit: the router commits.

Unlocking (FR-2.1): the first module (by `position`) is always open. Any other module opens when
the one before it is complete, and stays as it is once the student has started it. A module with
no segments yet is passed over, so missing content never locks the rest of the course.

Progress (FR-2.5, FR-2.6): the student moves through a module one segment at a time. The
furthest segment reached is kept, so stepping back to reread never loses progress. A student moves
past a segment only once it is done (FR-2.7): an activity segment once they have answered its
activity at least once, right or wrong, and a video segment once they have passed every one of
the video's checkpoints. Every other kind is done when shown. An activity whose kind has no
student UI yet (`KINDS_WITHOUT_STUDENT_UI`) counts as done, so it can't strand a student. The
module is complete, for good, once its last segment is done.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Checkpoint, Module, ModuleProgress, Segment, Video
from app.schemas.modules import (
    ModuleDetailOut,
    ModuleOut,
    ModuleStatus,
    RetrievalActivityOut,
    SegmentOut,
)
from app.services.locking import lock_student

# Activity kinds the web can't show a student yet: it says "This activity kind is not available
# yet" instead (SUPPORTED in web/src/features/activities/ActivityRenderer.tsx is the mirror of
# this set). A student can't answer them, so FR-2.7 counts them as done rather than locking the
# student out of the rest of the module.
# TODO: remove a kind from this set as soon as its student UI exists.
KINDS_WITHOUT_STUDENT_UI: frozenset[str] = frozenset({"trace", "fix_the_bug", "choose_tests"})


class ModuleNotFound(ValueError):
    """No module has this id."""


class ModuleLocked(ValueError):
    """The module before this one isn't complete yet."""


class PositionTooFar(ValueError):
    """The position is more than one segment past the furthest the student has reached."""


class RetrievalIncomplete(ValueError):
    """The student has not answered every retrieval item before starting the module."""


class SegmentNotDone(ValueError):
    """The student tried to move past a segment they haven't done yet."""


def _modules(session: Session) -> Sequence[Module]:
    return session.scalars(select(Module).order_by(Module.position)).all()


def _progress(session: Session, user_id: int) -> dict[int, ModuleProgress]:
    rows = session.scalars(select(ModuleProgress).where(ModuleProgress.user_id == user_id))
    return {row.module_id: row for row in rows}


def _segments(session: Session, module_id: int) -> Sequence[Segment]:
    return session.scalars(
        select(Segment).where(Segment.module_id == module_id).order_by(Segment.position)
    ).all()


def _segment_counts(session: Session) -> dict[int, int]:
    counts: dict[int, int] = {}
    for module_id in session.scalars(
        select(Segment.module_id).where(Segment.module_id.isnot(None))
    ):
        if module_id is not None:
            counts[module_id] = counts.get(module_id, 0) + 1
    return counts


def _statuses(
    modules: Sequence[Module], progress: dict[int, ModuleProgress], counts: dict[int, int]
) -> dict[int, ModuleStatus]:
    """Each module's status for one student, in map order (FR-2.1).

    A module with no segments yet (its content hasn't been written) can't be completed, so it
    doesn't hold back the modules after it: it opens when they would, and unlocking passes over
    it. Once it has content it counts like any other.
    """
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
        if counts.get(module.id, 0) > 0:
            previous_complete = status == "complete"
    return statuses


def _status(session: Session, user_id: int, module_id: int) -> ModuleStatus:
    modules = _modules(session)
    if not any(module.id == module_id for module in modules):
        raise ModuleNotFound(module_id)
    return _statuses(modules, _progress(session, user_id), _segment_counts(session))[module_id]


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
    counts = _segment_counts(session)
    statuses = _statuses(modules, progress, counts)
    return [
        _summary(module, statuses[module.id], counts.get(module.id, 0), progress.get(module.id))
        for module in modules
    ]


def _videos(session: Session, segments: Sequence[Segment]) -> dict[int, int]:
    """Each video segment's video, by segment id. A video points at the segment that plays it
    (Video.segment_id): videos are made in the app."""
    return {
        video.segment_id: video.id
        for video in session.scalars(
            select(Video).where(Video.segment_id.in_([segment.id for segment in segments]))
        )
        if video.segment_id is not None
    }


def done_segments(session: Session, user_id: int, segments: Sequence[Segment]) -> set[int]:
    """The ids of the segments this student has done (FR-2.7). An activity segment is done once
    they have answered its activity at least once, and a video segment once they have passed
    every checkpoint in its video. A segment with nothing to do (any other kind, or no activity
    or video yet) is always done, and so is an activity, or a checkpoint, whose kind has no
    student UI yet (`KINDS_WITHOUT_STUDENT_UI`)."""
    videos = _videos(session, segments)
    checkpoints: dict[int, set[int]] = {}
    for video_id, activity_id in session.execute(
        select(Checkpoint.video_id, Checkpoint.activity_id).where(
            Checkpoint.video_id.in_(videos.values())
        )
    ):
        checkpoints.setdefault(video_id, set()).add(activity_id)
    wanted = {s.activity_id for s in segments if s.kind == "activity" and s.activity_id}
    wanted |= {a for ids in checkpoints.values() for a in ids}
    # Nobody can answer these yet, so they count as answered and passed.
    no_ui = set(
        session.scalars(
            select(Activity.id).where(
                Activity.id.in_(wanted), Activity.kind.in_(KINDS_WITHOUT_STUDENT_UI)
            )
        )
    )
    answered: set[int] = set(no_ui)
    passed: set[int] = set(no_ui)
    for activity_id, correct in session.execute(
        select(Attempt.activity_id, Attempt.correct).where(
            Attempt.user_id == user_id, Attempt.activity_id.in_(wanted)
        )
    ):
        answered.add(activity_id)
        if correct:
            passed.add(activity_id)
    done: set[int] = set()
    for segment in segments:
        if segment.kind == "activity" and segment.activity_id is not None:
            if segment.activity_id in answered:
                done.add(segment.id)
        elif segment.kind == "video" and segment.id in videos:
            if checkpoints.get(videos[segment.id], set()) <= passed:
                done.add(segment.id)
        else:
            done.add(segment.id)
    return done


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
    answered = _answered(session, user_id, [activity.id for activity in retrieval])
    videos = _videos(session, segments)
    done = done_segments(session, user_id, segments)
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
                done=segment.id in done,
            )
            for index, segment in enumerate(segments)
        ],
        retrieval=[
            RetrievalActivityOut(
                id=activity.id, title=activity.title, answered=activity.id in answered
            )
            for activity in retrieval
        ],
    )


def _answered(session: Session, user_id: int, activity_ids: Sequence[int]) -> set[int]:
    """Which of these activities the student has made at least one attempt at."""
    return set(
        session.scalars(
            select(Attempt.activity_id).where(
                Attempt.user_id == user_id, Attempt.activity_id.in_(activity_ids)
            )
        )
    )


def save_position(
    session: Session, user_id: int, module_id: int, segment_position: int
) -> ModuleProgress:
    """Record that the student reached `segment_position` (0-based) in this module.

    The furthest position reached is kept: stepping back is allowed and changes nothing. Moving
    more than one segment past the furthest raises `PositionTooFar`, and moving past a segment
    the student hasn't done raises `SegmentNotDone` (FR-2.7). The module is complete once the
    furthest position is the last segment and that segment is done, so saving the last segment
    again after doing it completes the module (the page's "Finish module"); saving it while it
    isn't done yet changes nothing. A complete module stays complete (FR-2.6). Raises
    `ModuleNotFound` or `ModuleLocked` like `get_module_detail`.

    Raises `RetrievalIncomplete` until the student has answered the module's retrieval questions
    (FR-2.4), unless the module is already complete: a student who finished it before its
    questions were added can still go back over it.

    Takes the student's write lock first (app/services/locking.py): the `FOR UPDATE` on the
    progress row below locks nothing before the first save has made that row, so two first saves
    at once (a double-clicked "Next") both inserted one and the second failed with a 500 (#138).
    """
    lock_student(session, user_id)
    status = _status(session, user_id, module_id)
    if status == "locked":
        raise ModuleLocked(module_id)
    if status != "complete":
        retrieval_ids = session.scalars(
            select(Activity.id).where(
                Activity.module_id == module_id, Activity.purpose == "retrieval"
            )
        ).all()
        if not set(retrieval_ids) <= _answered(session, user_id, retrieval_ids):
            raise RetrievalIncomplete(module_id)
    segments = _segments(session, module_id)
    last = len(segments) - 1
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
    done = done_segments(session, user_id, segments)
    # Only moving on leaves a segment behind. Saving a position already reached (stepping back
    # then forward again, or "Finish module" on a last segment that isn't done) moves past
    # nothing, so it isn't refused: it just doesn't complete the module (below).
    if (
        status != "complete"
        and segment_position > reached
        and segments[segment_position - 1].id not in done
    ):
        raise SegmentNotDone(module_id)
    if row is None:
        row = ModuleProgress(user_id=user_id, module_id=module_id, status="in_progress")
        session.add(row)
    row.current_segment_position = max(reached, segment_position)
    if (
        row.status != "complete"
        and row.current_segment_position == last
        and segments[last].id in done
    ):
        row.status = "complete"
        row.completed_at = datetime.now(tz=UTC)
    session.flush()
    return row
