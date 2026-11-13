"""The module map and each student's progress through the modules (SE document §9, FR-2).

The modules and their segments are content (app/models/content.py, loaded from the fixtures);
`ModuleProgress` is the student's part. Functions take a session and the student's id, flush
and never commit: the router commits.

Unlocking (FR-2.1): the first module (by `position`) is always open. Any other module opens when
the one before it is complete, and stays as it is once the student has started it. A module with
no segments yet is passed over, so missing content never locks the rest of the course.

Progress (FR-2.5, FR-2.6): the student moves through a module one segment at a time. The
furthest segment reached is kept, so stepping back to reread never loses progress. A student moves
past a segment only once it is done (FR-2.7): a practice activity once they have answered it
correctly, or after its last hint; a mastery or diagnostic item once they have answered it at all,
since only the first answer counts there; and a video segment once they have passed every one of
the video's checkpoints. Every other kind is done when shown. An activity whose kind has no
student UI yet (`KINDS_WITHOUT_STUDENT_UI`) counts as done, so it can't strand a student. The
module is complete, for good, once its last segment is done.

Support (FR-8.4, app/services/support.py): a support segment the student doesn't need is hidden.
It stays in the list, so positions never shift, and counts as done: the student moves straight
past it, and a module whose remaining segments are all hidden is complete once the last segment
shown is done.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Checkpoint, Hint, Module, ModuleProgress, Segment, Video
from app.schemas.modules import (
    ModuleDetailOut,
    ModuleOut,
    ModuleStatus,
    RetrievalActivityOut,
    SegmentOut,
)
from app.services import rewards
from app.services.events import log_event
from app.services.locks import lock_student
from app.services.mastery import MASTERY_MODULE
from app.services.support import hidden_segments, record_shown

# Activity kinds the web can't show a student yet: it says "This activity kind is not available
# yet" instead (SUPPORTED in web/src/features/activities/ActivityRenderer.tsx is the mirror of
# this set). A student can't answer them, so FR-2.7 counts them as done rather than locking the
# student out of the rest of the module. Empty since trace, fix_the_bug and choose_tests got their
# screens (#136); kept so a kind added to the API before its screen can't strand a student.
# Remove a kind from this set in the same change that adds it to SUPPORTED.
KINDS_WITHOUT_STUDENT_UI: frozenset[str] = frozenset()

# Purposes where one real answer is enough to move on (FR-2.7): the mastery check, where only the
# first answer counts (FR-7.1), and module 0's diagnostic, which finds gaps rather than gating.
ONE_ANSWER_PURPOSES: frozenset[str] = frozenset({"mastery", "diagnostic"})

# Purposes a student may skip (FR-8.3): a bonus quest is optional extra challenge, so its segment is
# done whether or not it is answered, and Next is never held back by it.
OPTIONAL_PURPOSES: frozenset[str] = frozenset({"bonus"})


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


def _locked(session: Session, user_id: int, module_ids: set[int]) -> bool:
    """True if there are modules here and every one is still locked for this student."""
    if not module_ids:
        return False
    statuses = _statuses(_modules(session), _progress(session, user_id), _segment_counts(session))
    return all(statuses.get(module_id, "locked") == "locked" for module_id in module_ids)


def segment_locked(session: Session, user_id: int, segment_id: int) -> bool:
    """Whether this segment is in a module still locked for this student."""
    module_id = session.scalar(select(Segment.module_id).where(Segment.id == segment_id))
    return module_id is not None and _locked(session, user_id, {module_id})


def _summary(
    module: Module,
    status: ModuleStatus,
    segment_count: int,
    row: ModuleProgress | None,
    hidden_positions: frozenset[int] = frozenset(),
) -> ModuleOut:
    position = row.current_segment_position if row else 0
    if position > segment_count - 1:
        # Staff shortened the module (#128) below where the student had got to: open on its last
        # segment the student is shown, so the page lands on one that exists (#146).
        position = max(segment_count - 1, 0)
        while position > 0 and position in hidden_positions:
            position -= 1
    return ModuleOut(
        id=module.id,
        number=module.id,
        slug=module.slug,
        title=module.title,
        goals=module.goals,
        estimated_minutes=module.estimated_minutes,
        status=status,
        segment_count=segment_count,
        current_segment_position=position,
        shown_segment_count=segment_count - len(hidden_positions),
        shown_segments_passed=position - sum(1 for p in hidden_positions if p < position),
        restarted=row is not None and row.restarted_after_attempt is not None,
        can_restart=row is not None and row.status == "complete" and module.id != MASTERY_MODULE,
    )


def _hidden_positions(segments: Sequence[Segment], hidden: set[int]) -> frozenset[int]:
    return frozenset(index for index, segment in enumerate(segments) if segment.id in hidden)


def _hidden_by_module(
    session: Session, user_id: int, progress: dict[int, ModuleProgress]
) -> dict[int, frozenset[int]]:
    """The positions of the segments hidden from this student, for each module with support
    segments (FR-8.4). Other modules hide nothing."""
    with_support = set(
        session.scalars(
            select(Segment.module_id).where(
                Segment.module_id.is_not(None), Segment.support_for.is_not(None)
            )
        )
    )
    hidden: dict[int, frozenset[int]] = {}
    for module_id in with_support:
        if module_id is None:
            continue
        segments = _segments(session, module_id)
        found = hidden_segments(session, user_id, segments, progress.get(module_id))
        hidden[module_id] = _hidden_positions(segments, found)
    return hidden


def get_modules_for_user(session: Session, user_id: int) -> list[ModuleOut]:
    """Every module in map order, with this student's status and progress."""
    modules = _modules(session)
    progress = _progress(session, user_id)
    counts = _segment_counts(session)
    statuses = _statuses(modules, progress, counts)
    hidden = _hidden_by_module(session, user_id, progress)
    return [
        _summary(
            module,
            statuses[module.id],
            counts.get(module.id, 0),
            progress.get(module.id),
            hidden.get(module.id, frozenset()),
        )
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


def done_segments(
    session: Session, user_id: int, segments: Sequence[Segment], after: int | None = None
) -> set[int]:
    """The ids of the segments this student has done (FR-2.7).

    A practice activity is done once they have answered it correctly, or answered it after its
    last hint was shown (#143): the last hint gives the answer away, so a student who needed it can
    still move on. A mastery or diagnostic item (`ONE_ANSWER_PURPOSES`) is done once answered at
    all: only the first answer counts towards the report (FR-7.1) and the diagnostic finds gaps
    rather than gating, so asking for a right answer there would add steps that change nothing.
    A video segment is done once they have passed every checkpoint in its video. A segment with
    nothing to do (any other kind, or no activity or video yet) is always done, and so is an
    activity, or a checkpoint, whose kind has no student UI yet (`KINDS_WITHOUT_STUDENT_UI`)."""
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
    # Each activity's last hint level: an answer given after it was shown also counts.
    last_hint = dict(
        session.execute(
            select(Hint.activity_id, func.max(Hint.level))
            .where(Hint.activity_id.in_(wanted))
            .group_by(Hint.activity_id)
        ).all()
    )
    one_answer = set(
        session.scalars(
            select(Activity.id).where(
                Activity.id.in_(wanted), Activity.purpose.in_(ONE_ANSWER_PURPOSES)
            )
        )
    )
    optional = set(
        session.scalars(
            select(Activity.id).where(
                Activity.id.in_(wanted), Activity.purpose.in_(OPTIONAL_PURPOSES)
            )
        )
    )
    # done: answered correctly, or after the last hint; or optional (a bonus quest)
    answered: set[int] = set(no_ui) | optional
    passed: set[int] = set(no_ui)
    attempts = select(Attempt.activity_id, Attempt.correct, Attempt.hint_level).where(
        Attempt.user_id == user_id, Attempt.activity_id.in_(wanted)
    )
    if after is not None:  # a restarted module: only answers since then (app/services/restart.py)
        attempts = attempts.where(Attempt.id > after)
    for activity_id, correct, hint_level in session.execute(attempts):
        last = last_hint.get(activity_id)
        if correct or activity_id in one_answer or (last is not None and hint_level >= last):
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


def course_minutes(session: Session) -> int:
    """The whole course's estimated length: the sum of every module's `estimated_minutes`, from
    the fixtures. The one number the register page and the module map both show (#146)."""
    return int(session.scalar(select(func.coalesce(func.sum(Module.estimated_minutes), 0))) or 0)


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
    hidden = hidden_segments(session, user_id, segments, row)  # support not needed (FR-8.4)
    retrieval = session.scalars(
        select(Activity)
        .where(Activity.module_id == module_id, Activity.purpose == "retrieval")
        .order_by(Activity.id)
    ).all()
    # A restarted module shows every question afresh: only answers since then count here.
    after = row.restarted_after_attempt if row is not None else None
    answered = _answered(session, user_id, [activity.id for activity in retrieval], after)
    videos = _videos(session, segments)
    done = done_segments(session, user_id, segments, after)
    optional = set(
        session.scalars(
            select(Activity.id).where(
                Activity.id.in_([s.activity_id for s in segments if s.activity_id]),
                Activity.purpose.in_(OPTIONAL_PURPOSES),
            )
        )
    )
    attempted = _answered(
        session, user_id, [s.activity_id for s in segments if s.activity_id], after
    )
    # TODO (FR-8.1): leave out the refreshers module 0's diagnostic has ruled out, once the
    # diagnostic records its result. Until then every refresher is shown.
    detail = ModuleDetailOut(
        **_summary(
            module, status, len(segments), row, _hidden_positions(segments, hidden)
        ).model_dump(),
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
                attempted=segment.activity_id is not None and segment.activity_id in attempted,
                optional=segment.activity_id is not None and segment.activity_id in optional,
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
    # Support segments (FR-8.4): which objective each is for, and the ones this student doesn't
    # need are hidden and count as done, so they never hold the student up.
    support_for = {segment.id: segment.support_for for segment in segments}
    for out in detail.segments:
        out.support_for = support_for.get(out.id)
        if out.id in hidden:
            out.shown = False
            out.done = True
    return detail


def segment_order(session: Session, module_id: int) -> list[int]:
    """The ids of a module's segments, in order: what `keep_places` needs from before a change."""
    return [segment.id for segment in _segments(session, module_id)]


def keep_places(session: Session, module_id: int, before: Sequence[int]) -> int:
    """After a module's segments changed (the seed, or a staff edit), keep every student on the
    segment they had reached, not on the number (FR-2.5). `before` is the module's segment ids in
    their old order (`segment_order`). A student's position is moved to where their segment is
    now; if it was taken out, to where the nearest segment before it is now. Without this, support
    segments (#172) put in before a student's place would move them back to content they had done,
    and one taken out would move them on to content they hadn't reached. Not committed. Returns how
    many students' positions moved."""
    after = segment_order(session, module_id)
    if list(before) == after:
        return 0
    now_at = {segment_id: index for index, segment_id in enumerate(after)}
    moved = 0
    for row in session.scalars(select(ModuleProgress).where(ModuleProgress.module_id == module_id)):
        reached = row.current_segment_position
        place = next(
            (now_at[s] for s in reversed(before[: reached + 1]) if s in now_at),
            0,
        )
        place = min(place, max(len(after) - 1, 0))
        if place != reached:
            row.current_segment_position = place
            moved += 1
    session.flush()
    return moved


def _answered(
    session: Session, user_id: int, activity_ids: Sequence[int], after: int | None = None
) -> set[int]:
    """Which of these activities the student has made at least one attempt at (only attempts with
    an id above `after`, if given: since the module's restart)."""
    query = select(Attempt.activity_id).where(
        Attempt.user_id == user_id, Attempt.activity_id.in_(activity_ids)
    )
    if after is not None:
        query = query.where(Attempt.id > after)
    return set(session.scalars(query))


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

    Support segments the student doesn't need (FR-8.4) are hidden and done: "one segment" means
    the next one shown, so a save may jump over hidden ones, and "the last segment" means the
    last one shown. Every support segment shown when the save is made is recorded as shown, so it
    stays shown (app/services/support.py).

    Raises `RetrievalIncomplete` until the student has answered the module's retrieval questions
    (FR-2.4), unless the module is already complete: a student who finished it before its
    questions were added can still go back over it.

    Takes the student's write lock first (app/services/locks.py): the `FOR UPDATE` on the
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
    # Support the student doesn't need is hidden: it is done, and Next moves straight past it, so
    # the next segment may be several positions on (FR-8.4). Support shown now stays shown.
    hidden = hidden_segments(session, user_id, segments, row)
    record_shown(session, user_id, segments, hidden)
    allowed = reached + 1
    while allowed < last and segments[allowed].id in hidden:
        allowed += 1
    if segment_position > min(allowed, last) or (
        segment_position > reached and segments[segment_position].id in hidden
    ):
        raise PositionTooFar(module_id)  # too far, or onto support this student isn't shown
    done = (
        done_segments(session, user_id, segments, row.restarted_after_attempt if row else None)
        | hidden
    )
    # Only moving on leaves a segment behind. Saving a position already reached (stepping back
    # then forward again, or "Finish module" on a last segment that isn't done) moves past
    # nothing, so it isn't refused: it just doesn't complete the module (below).
    if (
        status != "complete"
        and segment_position > reached
        and any(s.id not in done for s in segments[reached:segment_position])
    ):
        raise SegmentNotDone(module_id)
    if row is None:
        row = ModuleProgress(user_id=user_id, module_id=module_id, status="in_progress")
        session.add(row)
    row.current_segment_position = max(reached, segment_position)
    if (
        row.status != "complete"
        # Clamped to the last segment: a module shortened below the student's position (#128)
        # must still complete once its new last segment is done, or the student is stranded in
        # it (#146). Hidden support after the position counts as done (FR-8.4).
        and all(s.id in hidden for s in segments[min(row.current_segment_position, last) + 1 :])
        and segments[min(row.current_segment_position, last)].id in done
    ):
        row.status = "complete"
        row.completed_at = datetime.now(tz=UTC)
        # Once per module: a complete module stays complete (FR-10.1, #141). Its points and badge
        # come only with real work in it (FR-9.1, FR-9.6): see reward_module.
        log_event(session, user_id, "module_completed", f"module:{module_id}")
        reward_module(session, user_id, module_id)
    session.flush()
    return row


def _module_activities(session: Session, module_id: int) -> set[int]:
    """The activities a module asks for: those its segments show, and its own (recall questions).
    Not its optional bonus quests (FR-8.3), which earn their own reward (#87)."""
    shown = session.scalars(
        select(Segment.activity_id).where(
            Segment.module_id == module_id, Segment.activity_id.is_not(None)
        )
    )
    own = session.scalars(select(Activity.id).where(Activity.module_id == module_id))
    bonus = set(session.scalars(select(Activity.id).where(Activity.purpose.in_(OPTIONAL_PURPOSES))))
    return ({a for a in shown if a is not None} | set(own)) - bonus


def reward_module(session: Session, user_id: int, module_id: int) -> bool:
    """Give a complete module's 25 points, and the First Module badge with the first, once
    (FR-9.1, FR-9.3), if the student has done real work in it: at least one of its activities
    answered correctly without hint 3 or 4. A module walked through by opening every hint and
    sending anything earns nothing (FR-9.6, ID document §7.2: badges mark real progress, not
    clicks; #166 review). Called when the module completes, when such a right answer comes later,
    and by the seed for modules completed before this rule. Returns whether it was earned."""
    activities = _module_activities(session, module_id)
    earned = (
        session.scalar(
            select(Attempt.id)
            .where(
                Attempt.user_id == user_id,
                Attempt.activity_id.in_(activities),
                Attempt.correct.is_(True),
                rewards.real_work(),
            )
            .limit(1)
        )
        is not None
    )
    if earned:
        rewards.on_module_completed(session, user_id, module_id)  # points and badge once each
    return earned


def reward_completed_modules(session: Session, user_id: int, activity: Activity) -> None:
    """After a right answer without hint 3 or 4: a complete module of this activity's that hadn't
    earned its reward yet earns it now."""
    homes = set(
        session.scalars(
            select(Segment.module_id).where(
                Segment.activity_id == activity.id, Segment.module_id.is_not(None)
            )
        )
    )
    if activity.module_id is not None:
        homes.add(activity.module_id)
    complete = session.scalars(
        select(ModuleProgress.module_id).where(
            ModuleProgress.user_id == user_id,
            ModuleProgress.module_id.in_({m for m in homes if m is not None}),
            ModuleProgress.status == "complete",
        )
    )
    for module_id in complete:
        reward_module(session, user_id, module_id)


def backfill_module_rewards(session: Session) -> int:
    """Reward every complete module that has earned it but has no points yet: modules completed
    before module points were awarded (#166 review). Safe to run on every seed: points and badges
    are given once. Not committed. Returns how many modules gained their points."""
    gained = 0
    rows = session.scalars(select(ModuleProgress).where(ModuleProgress.status == "complete"))
    for row in list(rows):
        before = rewards.total_points(session, row.user_id)
        reward_module(session, row.user_id, row.module_id)
        gained += rewards.total_points(session, row.user_id) > before
    return gained
