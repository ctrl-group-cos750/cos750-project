"""The staff portal's "Accounts" pages: every account, one account's progress, and deleting one.
Staff only. Staff access itself is granted and removed with /api/staff/members."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import Select, distinct, func, select
from sqlalchemy.orm import Session

from app.auth import StaffUser
from app.db import DbSession
from app.models import Activity, Attempt, Checkpoint, HintView, User, Video
from app.schemas.accounts import (
    AccountAttempt,
    AccountDetail,
    AccountStats,
    AccountSummary,
    AccountVideo,
)
from app.schemas.ids import RowId
from app.services.history import delete_history
from app.services.locks import StudentGone, lock_student

router = APIRouter(prefix="/api/staff/accounts", tags=["staff"])

NOT_FOUND = "This account does not exist."
NOT_YOURSELF = "You can't delete your own account here. Ask another team member to do it."
RECENT = 10


def _last_active() -> Select[tuple[int, datetime]]:
    """Each user's latest attempt or hint view."""
    events = (
        select(Attempt.user_id.label("user_id"), Attempt.created_at.label("at"))
        .union_all(select(HintView.user_id, HintView.created_at))
        .subquery()
    )
    return select(events.c.user_id, func.max(events.c.at).label("at")).group_by(events.c.user_id)


def _summary(user: User, last_active_at: datetime | None) -> AccountSummary:
    return AccountSummary(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_staff=user.is_staff,
        created_at=user.created_at,
        last_active_at=last_active_at,
    )


def mask_email(email: str) -> str:
    """ "a•••@example.com": enough to tell two accounts apart, not enough to contact anyone."""
    local, _, domain = email.partition("@")
    return f"{local[:1]}•••@{domain}" if domain else "•••"


@router.get("")
def list_accounts(session: DbSession, _staff: StaffUser) -> list[AccountSummary]:
    """Every account, newest first. The portal searches this list as you type.

    Students' emails are masked here (NFR-S8, data minimisation, #146): a list of every student's
    address is more than staff need to find an account, and it would all leak at once from one
    staff session. Staff accounts keep their full email (the team's own). One account's page
    (below) still shows the full email, which staff need to act on it."""
    last = _last_active().subquery()
    rows = session.execute(
        select(User, last.c.at)
        .outerjoin(last, last.c.user_id == User.id)
        .order_by(User.created_at.desc(), User.id.desc())
    ).all()
    summaries = [_summary(user, at) for user, at in rows]
    for summary in summaries:
        if not summary.is_staff:
            summary.email = mask_email(summary.email)
    return summaries


def _stats(session: Session, user_id: int) -> AccountStats:
    attempts, correct, tried = session.execute(
        select(
            func.count(),
            func.count().filter(Attempt.correct.is_(True)),
            func.count(distinct(Attempt.activity_id)),
        ).where(Attempt.user_id == user_id)
    ).one()
    passed = session.scalar(
        select(func.count(distinct(Attempt.activity_id))).where(
            Attempt.user_id == user_id, Attempt.correct.is_(True)
        )
    )
    hints = session.scalar(select(func.count()).where(HintView.user_id == user_id))
    return AccountStats(
        attempts=attempts,
        correct_attempts=correct,
        activities_tried=tried,
        activities_passed=passed or 0,
        hints_viewed=hints or 0,
    )


def _videos(session: Session, user_id: int) -> list[AccountVideo]:
    passed = (
        select(Attempt.activity_id.label("activity_id"))
        .where(Attempt.user_id == user_id, Attempt.correct.is_(True))
        .distinct()
        .subquery()
    )
    rows = session.execute(
        select(Video.id, Video.title, func.count(Checkpoint.id), func.count(passed.c.activity_id))
        .join(Checkpoint, Checkpoint.video_id == Video.id)
        .outerjoin(passed, passed.c.activity_id == Checkpoint.activity_id)
        .group_by(Video.id, Video.title)
        .order_by(Video.id)
    ).all()
    return [
        AccountVideo(id=vid, title=title, checkpoints_total=total, checkpoints_passed=done)
        for vid, title, total, done in rows
    ]


def _recent(session: Session, user_id: int) -> list[AccountAttempt]:
    rows = session.execute(
        select(Attempt, Activity.title, Activity.kind)
        .join(Activity, Activity.id == Attempt.activity_id)
        .where(Attempt.user_id == user_id)
        .order_by(Attempt.created_at.desc(), Attempt.id.desc())
        .limit(RECENT)
    ).all()
    return [
        AccountAttempt(
            id=attempt.id,
            activity_title=title,
            kind=kind,
            correct=attempt.correct,
            hint_level=attempt.hint_level,
            created_at=attempt.created_at,
        )
        for attempt, title, kind in rows
    ]


@router.get("/{user_id}")
def get_account(user_id: RowId, session: DbSession, _staff: StaffUser) -> AccountDetail:
    """One account: who they are, totals, progress through each video and their last 10 answers.
    What they answered is left out: staff see whether it was right, not the answer itself."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    times = [
        session.scalar(select(func.max(Attempt.created_at)).where(Attempt.user_id == user_id)),
        session.scalar(select(func.max(HintView.created_at)).where(HintView.user_id == user_id)),
    ]
    last_at = max((t for t in times if t is not None), default=None)
    return AccountDetail(
        **_summary(user, last_at).model_dump(),
        stats=_stats(session, user_id),
        videos=_videos(session, user_id),
        recent_attempts=_recent(session, user_id),
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(user_id: RowId, session: DbSession, staff: StaffUser) -> None:
    """Delete the account and everything stored about it (attempts, hint views, points, badges:
    every table of student history, app/services/history.py), in one
    transaction. Their session stops working at once: there is no user left to load. Nobody can
    delete their own account here."""
    if user_id == staff.id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=NOT_YOURSELF)
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    # Wait for any answer, hint or position save the student has in flight, and hold the next
    # ones back, so none adds a row after their history is deleted (app/services/locks.py).
    try:
        lock_student(session, user_id)
    except StudentGone:  # another staff member deleted it first
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND) from None
    delete_history(session, user_id)
    session.delete(user)
    session.commit()
