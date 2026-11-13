"""Evaluation data for the ID team's pilot (FR-10, ID document §8): CSV downloads and the
"Pilot insights" page. Staff only.

Students are identified by a pseudonym only, never by email, name or account id (FR-10.3): the same
pseudonym in every file, so the files join, but not the number in /staff/accounts/<id>, so a row
can't be traced back to a person from the portal (13 Nov audit, A13). Staff and
demo accounts are left out: the team's own testing, and the demo accounts' replayed histories
(app/seed/demo_accounts.py), would otherwise count as pilot students.
"""

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter
from fastapi.responses import Response
from sqlalchemy import Select, distinct, func, select

from app.auth import StaffUser
from app.db import DbSession
from app.models import (
    Activity,
    Attempt,
    Checkpoint,
    Event,
    HintView,
    Objective,
    ObjectiveResult,
    User,
    Video,
)
from app.schemas.evaluation import (
    ActivityInsight,
    CheckpointInsight,
    CommonWrongAnswer,
    Insights,
    ObjectiveReadiness,
    Readiness,
    VideoInsight,
)
from app.services.pseudonym import pseudonym

router = APIRouter(prefix="/api/staff", tags=["staff"])

SUPPORT_LEVEL = 3  # hint levels 3 and 4 make a correct answer count as "with support" (FR-7.2)
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _students() -> Select[int]:
    """The ids of every real student: not staff, not a seeded demo account."""
    return select(User.id).where(User.is_staff.is_(False), User.is_demo.is_(False))


def _cell(value: Any) -> str:
    """A CSV cell. JSON for dicts and lists; a leading ' on anything a spreadsheet would run as a
    formula, so a title or an answer can never execute in the ID team's Excel."""
    if isinstance(value, dict | list):
        text = json.dumps(value, separators=(",", ":"), sort_keys=True)
    elif isinstance(value, datetime):
        text = value.isoformat()
    elif value is None:
        text = ""
    else:
        text = str(value)
    return "'" + text if text.startswith(FORMULA_START) else text


def _csv(name: str, header: list[str], rows: list[list[Any]]) -> Response:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    writer.writerows([[_cell(v) for v in row] for row in rows])
    day = datetime.now(UTC).date().isoformat()
    return Response(
        out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="ctrl-academy-{name}-{day}.csv"'},
    )


@router.get("/export/{table}.csv", response_class=Response)
def export_csv(
    table: Literal["attempts", "hints", "events", "objective_results"],
    session: DbSession,
    _staff: StaffUser,
) -> Response:
    """Download one table as CSV for every real student (FR-10.2), oldest first:

    - `attempts`: each answer; `submitted` and `detail` are what was answered and the per-part
      result, as JSON.
    - `hints`: each hint shown. `round` is which time through its module (0, then one more for
      each restart, app/services/restart.py); `after_attempt` is the newest attempt id when it
      was shown, so it came before exactly that student's attempts with a higher `attempt_id`.
    - `events`: the timeline (app/services/events.py): videos started and finished, checkpoints
      reached, segments viewed, hints shown, results changing, modules completed and restarted,
      quick checks taken; `payload` as JSON. Segment views and module completions give time per segment and per
      module. Each `module_restarted` carries its `round` and `after_attempt`: a student's
      attempts at that module's activities with an id above one restart's `after_attempt`, and
      not above the next one's, are that round's.
    - `objective_results`: each student's current result per objective, with the attempts it was
      decided from (`evidence`).
    """
    if table == "events":
        return _csv(
            "events",
            ["event_id", "student", "type", "ref", "payload", "created_at"],
            [
                [e.id, pseudonym(e.user_id), e.type, e.ref, e.payload, e.created_at]
                for e in session.scalars(
                    select(Event)
                    .where(Event.user_id.in_(_students()))
                    .order_by(Event.created_at, Event.id)
                )
            ],
        )
    if table == "objective_results":
        return _csv(
            "objective-results",
            ["student", "objective_id", "state", "evidence", "updated_at"],
            # By pseudonym, not by account id: rows in id order would give away who joined first
            # (#215 review).
            sorted(
                (
                    [pseudonym(r.user_id), r.objective_id, r.state, r.evidence, r.updated_at]
                    for r in session.scalars(
                        select(ObjectiveResult).where(ObjectiveResult.user_id.in_(_students()))
                    )
                ),
                key=lambda row: (row[0], row[1]),
            ),
        )
    if table == "attempts":
        rows = session.execute(
            select(Attempt, Activity.title, Activity.kind)
            .join(Activity, Activity.id == Attempt.activity_id)
            .where(Attempt.user_id.in_(_students()))
            .order_by(Attempt.created_at, Attempt.id)
        ).all()
        return _csv(
            "attempts",
            [
                "attempt_id",
                "student",
                "activity_id",
                "activity_title",
                "activity_kind",
                "correct",
                "score",
                "hint_level",
                "submitted",
                "detail",
                "created_at",
            ],
            [
                [
                    a.id,
                    pseudonym(a.user_id),
                    a.activity_id,
                    title,
                    kind,
                    a.correct,
                    a.score,
                    a.hint_level,
                    a.submitted,
                    a.detail,
                    a.created_at,
                ]
                for a, title, kind in rows
            ],
        )
    hints = session.execute(
        select(HintView, Activity.title)
        .join(Activity, Activity.id == HintView.activity_id)
        .where(HintView.user_id.in_(_students()))
        .order_by(HintView.created_at, HintView.id)
    ).all()
    return _csv(
        "hints",
        [
            "hint_view_id",
            "student",
            "activity_id",
            "activity_title",
            "level",
            "round",
            "after_attempt",
            "created_at",
        ],
        [
            [
                h.id,
                pseudonym(h.user_id),
                h.activity_id,
                title,
                h.level,
                h.round,
                h.after_attempt,
                h.created_at,
            ]
            for h, title in hints
        ],
    )


def _activity_insights(session: DbSession) -> list[ActivityInsight]:
    students = _students()
    tried = session.execute(
        select(
            Attempt.activity_id,
            func.count(distinct(Attempt.user_id)),
            func.count(),
            func.count().filter(Attempt.correct.is_(False)),
        )
        .where(Attempt.user_id.in_(students))
        .group_by(Attempt.activity_id)
    ).all()
    passed = dict(
        session.execute(
            select(Attempt.activity_id, func.count(distinct(Attempt.user_id)))
            .where(Attempt.user_id.in_(students), Attempt.correct.is_(True))
            .group_by(Attempt.activity_id)
        ).all()
    )
    # Needed hint 3 or 4: shown it before ever answering correctly. Hints opened on a question
    # already solved, after restarting its module, are practice, not support it needed (#211).
    solved_before = (
        select(Attempt.id)
        .where(
            Attempt.user_id == HintView.user_id,
            Attempt.activity_id == HintView.activity_id,
            Attempt.correct.is_(True),
            Attempt.id <= HintView.after_attempt,
        )
        .exists()
    )
    support = dict(
        session.execute(
            select(HintView.activity_id, func.count(distinct(HintView.user_id)))
            .where(
                HintView.user_id.in_(students),
                HintView.level >= SUPPORT_LEVEL,
                ~solved_before,
            )
            .group_by(HintView.activity_id)
        ).all()
    )
    ids = [row[0] for row in tried]
    activities = {a.id: a for a in session.scalars(select(Activity).where(Activity.id.in_(ids)))}
    result = [
        ActivityInsight(
            id=activity_id,
            title=activities[activity_id].title,
            kind=activities[activity_id].kind,
            students=n_students,
            attempts=n_attempts,
            wrong_attempts=n_wrong,
            students_passed=passed.get(activity_id, 0),
            students_with_support=support.get(activity_id, 0),
        )
        for activity_id, n_students, n_attempts, n_wrong in tried
    ]
    # The ones students struggled with most come first.
    return sorted(result, key=lambda a: (-a.wrong_attempts, -a.students_with_support, a.id))


def _video_insights(session: DbSession) -> list[VideoInsight]:
    students = _students()
    rows = session.execute(
        select(Video, Checkpoint, Activity.title)
        .join(Checkpoint, Checkpoint.video_id == Video.id)
        .join(Activity, Activity.id == Checkpoint.activity_id)
        .order_by(Video.id, Checkpoint.at_seconds, Checkpoint.id)
    ).all()
    passed = dict(
        session.execute(
            select(Attempt.activity_id, func.count(distinct(Attempt.user_id)))
            .where(Attempt.user_id.in_(students), Attempt.correct.is_(True))
            .group_by(Attempt.activity_id)
        ).all()
    )
    videos: dict[int, VideoInsight] = {}
    activity_ids: dict[int, list[int]] = {}
    for video, checkpoint, title in rows:
        insight = videos.setdefault(
            video.id,
            VideoInsight(id=video.id, title=video.title, students=0, finished=0, checkpoints=[]),
        )
        insight.checkpoints.append(
            CheckpointInsight(
                id=checkpoint.id,
                at_seconds=checkpoint.at_seconds,
                activity_title=title,
                students_passed=passed.get(checkpoint.activity_id, 0),
            )
        )
        activity_ids.setdefault(video.id, []).append(checkpoint.activity_id)
    for video_id, insight in videos.items():
        ref = f"video:{video_id}"
        started = select(Event.user_id).where(
            Event.user_id.in_(students), Event.type == "video_started", Event.ref == ref
        )
        answered = select(Attempt.user_id).where(
            Attempt.user_id.in_(students), Attempt.activity_id.in_(activity_ids[video_id])
        )
        insight.students = (
            session.scalar(select(func.count()).select_from(started.union(answered).subquery()))
            or 0
        )
        insight.finished = (
            session.scalar(
                select(func.count(distinct(Event.user_id))).where(
                    Event.user_id.in_(students), Event.type == "video_completed", Event.ref == ref
                )
            )
            or 0
        )
    return list(videos.values())


@router.get("/insights")
def insights(session: DbSession, _staff: StaffUser) -> Insights:
    """The pilot at a glance (ID document §8.4): per activity, how many students tried it, wrong
    attempts, and how many needed hint 3 or 4; per video, how many started it, passed each
    checkpoint and finished it, which shows where students stopped. Real students only (no staff
    or demo accounts); counts only."""
    students = _students()
    attempts = session.scalar(select(func.count()).where(Attempt.user_id.in_(students))) or 0
    hints = session.scalar(select(func.count()).where(HintView.user_id.in_(students))) or 0
    active = session.scalar(
        select(func.count()).select_from(
            select(Attempt.user_id)
            .where(Attempt.user_id.in_(students))
            .union(
                select(HintView.user_id).where(HintView.user_id.in_(students)),
                select(Event.user_id).where(Event.user_id.in_(students)),
            )
            .subquery()
        )
    )
    return Insights(
        students=active or 0,
        attempts=attempts,
        hints_viewed=hints,
        activities=_activity_insights(session),
        videos=_video_insights(session),
    )


@router.get("/readiness")
def readiness(session: DbSession, _staff: StaffUser) -> Readiness:
    """For the lecturer, before the lecture (FR-10): how many students who took the mastery check
    are ready, each objective's results across them, and the most common wrong first answers on
    the assessed multiple-choice items (module 6 and the review paths' fresh items), each with the
    content's explanation of why it is wrong. Real students only; counts only, no names."""
    students = _students()
    objectives = list(session.scalars(select(Objective).order_by(Objective.id)))
    counts: dict[tuple[int, str], int] = {
        (objective_id, state): n
        for objective_id, state, n in session.execute(
            select(ObjectiveResult.objective_id, ObjectiveResult.state, func.count())
            .where(ObjectiveResult.user_id.in_(students))
            .group_by(ObjectiveResult.objective_id, ObjectiveResult.state)
        )
    }
    assessed = select(Activity.id).where(Activity.purpose == "mastery")
    took = (
        session.scalar(
            select(func.count(distinct(Attempt.user_id))).where(
                Attempt.user_id.in_(students), Attempt.activity_id.in_(assessed)
            )
        )
        or 0
    )
    met = (
        select(ObjectiveResult.user_id)
        .where(
            ObjectiveResult.user_id.in_(students),
            ObjectiveResult.state.in_(("met_independently", "met_with_support")),
        )
        .group_by(ObjectiveResult.user_id)
        .having(func.count() == len(objectives))
    )
    ready = session.scalar(select(func.count()).select_from(met.subquery())) or 0
    return Readiness(
        students=took,
        ready=ready,
        objectives=[
            ObjectiveReadiness(
                id=o.id,
                text=o.text,
                met_independently=counts.get((o.id, "met_independently"), 0),
                met_with_support=counts.get((o.id, "met_with_support"), 0),
                not_yet=counts.get((o.id, "not_yet"), 0),
            )
            for o in objectives
        ],
        common_wrong_answers=_common_wrong_answers(session),
    )


def _common_wrong_answers(session: DbSession, top: int = 10) -> list[CommonWrongAnswer]:
    """Each assessed multiple-choice item's most chosen wrong option at first answer, most wrong
    first. Only the first answer counts on an assessed item (FR-7.1), so it is the honest one."""
    items = {
        a.id: a
        for a in session.scalars(
            select(Activity).where(
                Activity.purpose == "mastery", Activity.kind == "multiple_choice"
            )
        )
    }
    if not items:
        return []
    first: dict[tuple[int, int], Attempt] = {}
    for attempt in session.scalars(
        select(Attempt)
        .where(Attempt.user_id.in_(_students()), Attempt.activity_id.in_(items))
        .order_by(Attempt.created_at, Attempt.id)
    ):
        first.setdefault((attempt.user_id, attempt.activity_id), attempt)
    answered: dict[int, int] = {}
    wrong: dict[int, dict[str, int]] = {}
    for (_user, activity_id), attempt in first.items():
        answered[activity_id] = answered.get(activity_id, 0) + 1
        if not attempt.correct:
            chosen = str(attempt.submitted.get("selected", ""))
            options = wrong.setdefault(activity_id, {})
            options[chosen] = options.get(chosen, 0) + 1
    result = []
    for activity_id, options in wrong.items():
        activity = items[activity_id]
        option_id, chosen_by = max(options.items(), key=lambda kv: (kv[1], kv[0]))
        labels = {o["id"]: o["label"] for o in activity.config.get("options", [])}
        feedback = (activity.solution or {}).get("feedback", {})
        result.append(
            CommonWrongAnswer(
                activity_id=activity_id,
                title=activity.title,
                objective_id=activity.objective_id,
                answered=answered[activity_id],
                wrong=sum(options.values()),
                option=labels.get(option_id, option_id),
                chosen_by=chosen_by,
                why_wrong=feedback.get(option_id),
            )
        )
    result.sort(key=lambda r: (-r.wrong, -r.chosen_by, r.activity_id))
    return result[:top]
