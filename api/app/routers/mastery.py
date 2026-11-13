from typing import Literal, cast

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.auth import CurrentUser
from app.db import DbSession
from app.models import Activity, Attempt, Segment
from app.schemas.content import SegmentKind
from app.schemas.ids import RowId
from app.schemas.mastery import (
    MasteryReportOut,
    ObjectiveReportOut,
    ReviewPathOut,
    ReviewProgressOut,
    ReviewStepOut,
)
from app.services.access import review_practice_done
from app.services.mastery import Tally, evaluate, is_ready, review_items

router = APIRouter(prefix="/api/me", tags=["mastery"])

NO_PATH = "This objective has no review path."
NOT_OPEN = "This review path opens when the mastery check marks the objective 'not yet'."


@router.get("/report")
def get_report(user: CurrentUser, session: DbSession) -> MasteryReportOut:
    """The logged-in student's mastery report: each objective's result, whether they are ready
    for the lecture, and the review path's progress for each objective module 6 marked "not yet"
    (FR-7.3 to FR-7.5).

    Worked out from their attempts on every request (app/services/mastery.py), so it always follows
    the current rules (FR-7.6). Nothing a client sends can set a result: they change only through
    attempts. Only ever the student's own."""
    outcomes = evaluate(session, user.id)
    return MasteryReportOut(
        ready=is_ready(outcomes),
        objectives=[
            ObjectiveReportOut(
                id=o.objective.id,
                text=o.objective.text,
                criterion=o.objective.criterion,
                state=o.state,
                answered=o.check.answered,
                total=o.check.total,
                review=(
                    ReviewProgressOut(answered=o.review.answered, total=o.review.total)
                    if o.review
                    else None
                ),
            )
            for o in outcomes
        ],
    )


@router.get("/review/{objective_id}")
def get_review_path(objective_id: RowId, user: CurrentUser, session: DbSession) -> ReviewPathOut:
    """The objective's review path: its steps in order, and which the student has answered
    (FR-7.5). 404 if the objective has no path; 403 until module 6 marks it "not yet", so the
    fresh items stay unseen until the student needs them. A fresh item is `locked` until the
    path's practice is done (review of 13 Nov). Staff may always open it, to preview."""
    segments = session.scalars(
        select(Segment)
        .where(Segment.review_objective_id == objective_id)
        .order_by(Segment.position)
    ).all()
    if not segments:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NO_PATH)
    outcome = next(o for o in evaluate(session, user.id) if o.objective.id == objective_id)
    review = outcome.review
    if review is None and user.is_staff:
        # Staff may open any review path to preview it, as they may any activity (#137). Its
        # progress counts their answers to the fresh items, which decide nothing for them.
        fresh = [a.id for a in review_items(session).get(objective_id, [])]
        answered_fresh = session.scalars(
            select(func.count(func.distinct(Attempt.activity_id))).where(
                Attempt.user_id == user.id, Attempt.activity_id.in_(fresh)
            )
        ).one()
        review = Tally("not_attempted", answered_fresh, len(fresh), ())
    if review is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=NOT_OPEN)

    activity_ids = [s.activity_id for s in segments if s.activity_id is not None]
    purposes = {
        a.id: a.purpose
        for a in session.scalars(select(Activity).where(Activity.id.in_(activity_ids)))
    }
    answered = set(
        session.scalars(
            select(Attempt.activity_id).where(
                Attempt.user_id == user.id, Attempt.activity_id.in_(activity_ids)
            )
        )
    )
    # Fresh items open once the practice is done (app/services/access.py, review of 13 Nov).
    practice_first = not user.is_staff and not review_practice_done(session, user.id, objective_id)
    return ReviewPathOut(
        objective_id=objective_id,
        objective_text=outcome.objective.text,
        criterion=outcome.objective.criterion,
        state=outcome.state,
        progress=ReviewProgressOut(answered=review.answered, total=review.total),
        steps=[
            ReviewStepOut(
                id=s.id,
                kind=cast(SegmentKind, s.kind),
                title=s.title,
                body=s.body,
                activity_id=s.activity_id,
                purpose=(
                    cast(Literal["review", "mastery"], purposes[s.activity_id])
                    if s.activity_id is not None
                    else None
                ),
                answered=s.activity_id in answered,
                locked=practice_first and purposes.get(s.activity_id or 0) == "mastery",
            )
            for s in segments
        ],
    )
