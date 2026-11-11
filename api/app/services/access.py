"""Which activities and videos a student may open (SE document FR-2.1, FR-3, FR-7.1, FR-7.5).

An activity is only usable where the course shows it, so that a locked module's activities, and
above all the mastery check's unseen items, can't be read, answered or hinted at early (#137).
Every place an activity can appear is one of its *homes*:

- **a module**: its own `module_id` (practice, retrieval, module 0's diagnostic, module 6's
  mastery items), a module segment that shows it, or a module segment that uses it as a skip
  check, if it is that module's or no module's, not a mastery item and on no review path. Open
  when the module is not locked for this student (`modules._statuses`, the module map's rule).
- **a review path**: a segment of an objective's review path. Open once module 6 has marked that
  objective "not yet" (`mastery.review_open`), so its fresh items stay unseen until then.
- **a video**: the question at one of the video's checkpoints. Open when the video is (below).

The activity is open if any of its homes is. One with no home at all (a retired fixture activity,
or a checkpoint question whose checkpoint was removed but which students had answered) is kept
for the evaluation data, but no student can open it any more.

A video placed on a module segment or a review-path segment follows that home. A video placed on
no segment (the staff video editor makes videos before anyone places them) stays open, as it was
before these checks, so a link to it keeps working; placing it in a module then gates it.

Staff (`users.is_staff`) may open everything, so they can preview any activity or video while
they write content. Their attempts are left out of the evaluation export (FR-10).
"""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Checkpoint, Segment, User, Video
from app.services.mastery import review_open
from app.services.modules import _modules, _progress, _segment_counts, _statuses

Refusal = Literal["module_locked", "review_closed", "retired"]


@dataclass(frozen=True)
class Homes:
    """Where an activity or video appears: module ids, review-path objective ids, video ids."""

    modules: frozenset[int] = frozenset()
    review_paths: frozenset[int] = frozenset()
    videos: frozenset[int] = frozenset()


def activity_homes(session: Session, activity: Activity) -> Homes:
    """Every module, review path and video this activity appears in.

    A segment's skip check (FR-8.2) is a home only for an activity that belongs to that module
    or to none, and never for a mastery item or an item on a review path: a segment naming
    another module's item, a module 6 item or a review path's item as its skip check must not
    open it early."""
    shown = session.execute(
        select(Segment.module_id, Segment.review_objective_id).where(
            Segment.activity_id == activity.id
        )
    ).all()
    checks = session.scalars(
        select(Segment.module_id).where(Segment.skip_check_activity_id == activity.id)
    ).all()
    modules = {m for m, _ in shown if m is not None}
    review_paths = frozenset(o for _, o in shown if o is not None)
    if activity.purpose != "mastery" and not review_paths:
        modules |= {m for m in checks if m is not None and activity.module_id in (None, m)}
    if activity.module_id is not None:
        modules.add(activity.module_id)
    videos = frozenset(
        session.scalars(select(Checkpoint.video_id).where(Checkpoint.activity_id == activity.id))
    )
    return Homes(
        modules=frozenset(modules),
        review_paths=review_paths,
        videos=videos,
    )


def _open_modules(session: Session, user_id: int) -> set[int]:
    """The modules this student may open: every one the module map doesn't show as locked."""
    statuses = _statuses(_modules(session), _progress(session, user_id), _segment_counts(session))
    return {module_id for module_id, status in statuses.items() if status != "locked"}


def _first_refusal(session: Session, user_id: int, homes: Homes) -> Refusal | None:
    """None if any home is open to this student; otherwise why the first one is shut."""
    if homes.modules & _open_modules(session, user_id):
        return None
    if any(review_open(session, user_id, objective) for objective in homes.review_paths):
        return None
    shut_videos: list[Refusal] = []
    for video in session.scalars(select(Video).where(Video.id.in_(homes.videos))):
        refusal = _video_refusal(session, user_id, video)
        if refusal is None:
            return None
        shut_videos.append(refusal)
    if homes.modules:
        return "module_locked"
    if homes.review_paths:
        return "review_closed"
    return shut_videos[0] if shut_videos else "retired"


def activity_refusal(session: Session, user: User, activity: Activity) -> Refusal | None:
    """None if this student may open the activity, else why not (see the module docstring)."""
    if user.is_staff:
        return None
    return _first_refusal(session, user.id, activity_homes(session, activity))


def _video_refusal(session: Session, user_id: int, video: Video) -> Refusal | None:
    if video.segment_id is None:
        return None
    segment = session.get_one(Segment, video.segment_id)
    return _first_refusal(
        session,
        user_id,
        Homes(
            modules=frozenset({segment.module_id} if segment.module_id is not None else ()),
            review_paths=frozenset(
                {segment.review_objective_id} if segment.review_objective_id is not None else ()
            ),
        ),
    )


def video_refusal(session: Session, user: User, video: Video) -> Refusal | None:
    """None if this student may open the video: it is on no segment yet, or its segment's module
    or review path is open (see the module docstring). Staff may open every video."""
    if user.is_staff:
        return None
    return _video_refusal(session, user.id, video)
