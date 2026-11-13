"""Which activities and videos a student may open (SE document FR-2.1, FR-3, FR-7.1, FR-7.5).

An activity is only usable where the course shows it, so that a locked module's activities, and
above all the mastery check's unseen items, can't be read, answered or hinted at early (#137).
Every place an activity can appear is one of its *homes*:

- **a module**: its own `module_id` (practice, retrieval, module 0's diagnostic, module 6's
  mastery items), a module segment that shows it, or a module segment that uses it as a skip
  check, if it is that module's or no module's, not a mastery item and on no review path. Open
  when the module is not locked for this student (`modules._statuses`, the module map's rule:
  since #214 only the mastery check is ever locked).
- **a review path**: a segment of an objective's review path. Open once module 6 has marked that
  objective "not yet" (`mastery.review_open`), so its fresh items stay unseen until then. A fresh
  item (purpose `mastery`, the ones that decide the result) opens only once the path's practice
  is done as a module's is (`modules.answer_states`: right, answered after the last hint, or
  answered twice): the path teaches before it tests, and the path page shows every step at once
  (review of 13 Nov, Critical 1).
- **a video**: the question at one of the video's checkpoints. Open when the video is (below).
- **a support segment** (FR-8.4, #172): an activity that a module shows only on support segments
  (`Segment.support_for`) is extra help for a struggling student. It is open only where one of
  those segments is shown to this student (`support.hidden_segments`) in a module that is open;
  its own `module_id` and any skip check don't open it, so a student who isn't shown the support
  can't reach it by id either, and its data stays that of students who were offered it.

The activity is open if any of its homes is. One with no home at all (a retired fixture activity,
or a checkpoint question whose checkpoint was removed but which students had answered) is kept
for the evaluation data, but no student can open it any more.

A video placed on a module segment or a review-path segment follows that home. A video placed on
no segment (the staff video editor makes videos before anyone places them) stays open, as it was
before these checks, so a link to it keeps working; placing it in a module then gates it.

A module's quick check questions (purpose `test_out`, FR-8.2, #214) are refused here altogether:
they are answered only through the quick check (app/services/quick_check.py), all together.

Staff (`users.is_staff`) may open everything, so they can preview any activity or video while
they write content. Their attempts are left out of the evaluation export (FR-10).
"""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Checkpoint, Segment, User, Video
from app.services.mastery import on_review_path, review_open
from app.services.modules import (
    _modules,
    _progress,
    _segment_counts,
    _segments,
    _statuses,
    answer_states,
)
from app.services.support import hidden_segments

Refusal = Literal[
    "module_locked", "review_closed", "practice_first", "not_shown", "retired", "quick_check"
]


@dataclass(frozen=True)
class Homes:
    """Where an activity or video appears: module ids, review-path objective ids, video ids and
    support segment ids."""

    modules: frozenset[int] = frozenset()
    review_paths: frozenset[int] = frozenset()
    videos: frozenset[int] = frozenset()
    support: frozenset[int] = frozenset()


def activity_homes(session: Session, activity: Activity) -> Homes:
    """Every module, review path and video this activity appears in.

    A segment's skip check (FR-8.2) is a home only for an activity that belongs to that module
    or to none, and never for a mastery item or an item on a review path: a segment naming
    another module's item, a module 6 item or a review path's item as its skip check must not
    open it early."""
    shown = session.execute(
        select(
            Segment.module_id, Segment.review_objective_id, Segment.support_for, Segment.id
        ).where(Segment.activity_id == activity.id)
    ).all()
    in_modules = [(m, support, segment) for m, _, support, segment in shown if m is not None]
    videos = frozenset(
        session.scalars(select(Checkpoint.video_id).where(Checkpoint.activity_id == activity.id))
    )
    if in_modules and all(support is not None for _, support, _ in in_modules):
        # Support only (FR-8.4): open where one of its support segments is shown, nowhere else.
        return Homes(
            review_paths=frozenset(o for _, o, _, _ in shown if o is not None),
            videos=videos,
            support=frozenset(segment for _, _, segment in in_modules),
        )
    checks = session.scalars(
        select(Segment.module_id).where(Segment.skip_check_activity_id == activity.id)
    ).all()
    modules = {m for m, _, _, _ in shown if m is not None}
    review_paths = frozenset(o for _, o, _, _ in shown if o is not None)
    # A practice item that is only a worked example's skip check is never shown: skipping a worked
    # example (FR-8.2) isn't built. Until it is, it has no home, so it can't be answered by its URL
    # for points (13 Nov audit). Module 0's diagnostic items are shown, and stay open.
    unused_check = bool(checks) and not shown and not videos and activity.purpose == "practice"
    if activity.purpose != "mastery" and not review_paths and not unused_check:
        modules |= {m for m in checks if m is not None and activity.module_id in (None, m)}
    if activity.module_id is not None and not unused_check:
        modules.add(activity.module_id)
    return Homes(
        modules=frozenset(modules),
        review_paths=review_paths,
        videos=videos,
    )


def _open_modules(session: Session, user_id: int) -> set[int]:
    """The modules this student may open: every one the module map doesn't show as locked."""
    statuses = _statuses(_modules(session), _progress(session, user_id), _segment_counts(session))
    return {module_id for module_id, status in statuses.items() if status != "locked"}


def _support_refusal(session: Session, user_id: int, segment_ids: frozenset[int]) -> Refusal | None:
    """None if one of these support segments is shown to this student in an open module."""
    if not segment_ids:
        return None
    open_modules = _open_modules(session, user_id)
    progress = _progress(session, user_id)
    refusal: Refusal = "module_locked"
    for module_id in set(
        session.scalars(select(Segment.module_id).where(Segment.id.in_(segment_ids)))
    ):
        if module_id is None or module_id not in open_modules:
            continue
        refusal = "not_shown"
        segments = _segments(session, module_id)
        hidden = hidden_segments(session, user_id, segments, progress.get(module_id))
        if any(s.id in segment_ids and s.id not in hidden for s in segments):
            return None
    return refusal


def _first_refusal(session: Session, user_id: int, homes: Homes) -> Refusal | None:
    """None if any home is open to this student; otherwise why the first one is shut."""
    if homes.modules & _open_modules(session, user_id):
        return None
    support = _support_refusal(session, user_id, homes.support)
    if homes.support and support is None:
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
    if support is not None:
        return support
    if homes.review_paths:
        return "review_closed"
    return shut_videos[0] if shut_videos else "retired"


def review_practice_done(session: Session, user_id: int, objective_id: int) -> bool:
    """Whether this student has done every practice item (purpose `review`) on the objective's
    review path, by the rule a module uses to let a student move on (FR-2.7)."""
    practice = list(
        session.scalars(
            select(Activity.id)
            .join(Segment, Segment.activity_id == Activity.id)
            .where(Segment.review_objective_id == objective_id, Activity.purpose == "review")
        )
    )
    return set(practice) <= answer_states(session, user_id, practice).done


def activity_refusal(session: Session, user: User, activity: Activity) -> Refusal | None:
    """None if this student may open the activity, else why not (see the module docstring)."""
    if user.is_staff:
        return None
    if activity.purpose == "test_out":
        # A quick check question is answered only in the quick check, all at once, with no hints
        # or feedback before the end (FR-8.2, #214): never one by one here.
        return "quick_check"
    homes = activity_homes(session, activity)
    refusal = _first_refusal(session, user.id, homes)
    # A fresh item waits for its path's practice (review of 13 Nov, Critical 1).
    if (
        refusal is None
        and on_review_path(activity)
        and homes.review_paths
        and not any(
            review_open(session, user.id, objective)
            and review_practice_done(session, user.id, objective)
            for objective in homes.review_paths
        )
    ):
        return "practice_first"
    return refusal


def _video_refusal(session: Session, user_id: int, video: Video) -> Refusal | None:
    if video.segment_id is None:
        return None
    segment = session.get_one(Segment, video.segment_id)
    if segment.support_for is not None and segment.module_id is not None:
        return _first_refusal(session, user_id, Homes(support=frozenset({segment.id})))
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
