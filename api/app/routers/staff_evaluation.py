"""Evaluation data for the ID team's pilot (FR-10, ID document §8): CSV downloads and the
"Pilot insights" page. Staff only.

Students are identified by their internal id only, never by email or name (FR-10.3). Staff and
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
    ObjectiveResult,
    User,
    Video,
)
from app.schemas.evaluation import ActivityInsight, CheckpointInsight, Insights, VideoInsight

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
    - `hints`: each hint shown.
    - `events`: the timeline (app/services/events.py): videos started and finished, checkpoints
      reached, segments viewed, hints shown, results changing, modules completed; `payload` as JSON.
      Segment views and module completions give time per segment and per module.
    - `objective_results`: each student's current result per objective, with the attempts it was
      decided from (`evidence`).
    """
    if table == "events":
        return _csv(
            "events",
            ["event_id", "user_id", "type", "ref", "payload", "created_at"],
            [
                [e.id, e.user_id, e.type, e.ref, e.payload, e.created_at]
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
            ["user_id", "objective_id", "state", "evidence", "updated_at"],
            [
                [r.user_id, r.objective_id, r.state, r.evidence, r.updated_at]
                for r in session.scalars(
                    select(ObjectiveResult)
                    .where(ObjectiveResult.user_id.in_(_students()))
                    .order_by(ObjectiveResult.user_id, ObjectiveResult.objective_id)
                )
            ],
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
                "user_id",
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
                    a.user_id,
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
        ["hint_view_id", "user_id", "activity_id", "activity_title", "level", "created_at"],
        [[h.id, h.user_id, h.activity_id, title, h.level, h.created_at] for h, title in hints],
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
    support = dict(
        session.execute(
            select(HintView.activity_id, func.count(distinct(HintView.user_id)))
            .where(HintView.user_id.in_(students), HintView.level >= SUPPORT_LEVEL)
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
