from fastapi import APIRouter

from app.auth import CurrentUser
from app.db import DbSession
from app.schemas.mastery import MasteryReportOut, ObjectiveReportOut
from app.services.mastery import evaluate, is_ready

router = APIRouter(prefix="/api/me", tags=["mastery"])


@router.get("/report")
def get_report(user: CurrentUser, session: DbSession) -> MasteryReportOut:
    """The logged-in student's mastery report: each objective's result and whether they are ready
    for the lecture (FR-7.3, FR-7.4).

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
                answered=o.answered,
                total=o.total,
            )
            for o in outcomes
        ],
    )
