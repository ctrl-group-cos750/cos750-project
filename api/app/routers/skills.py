from fastapi import APIRouter

from app.auth import CurrentUser
from app.db import DbSession
from app.schemas.skills import ModuleMedalOut, SkillOut, SkillsOut
from app.services.skills import module_medals, skills

router = APIRouter(prefix="/api/me", tags=["skills"])


@router.get("/skills")
def get_skills(user: CurrentUser, session: DbSession) -> SkillsOut:
    """The logged-in student's skill profile and module medals (FR-9.7, FR-9.8; #214).

    For each learning objective: how many of its practice items they have answered correctly, of
    how many, and its mastery result once the mastery check (or a review path) has decided it.
    For each module with activities to mark: its medal once complete, and the medal the answers so
    far are heading for. Worked out from attempts on each request (app/services/skills.py), so it
    follows the current content and rules. Only ever the student's own."""
    return SkillsOut(
        objectives=[
            SkillOut(
                id=s.objective_id, text=s.text, correct=s.correct, total=s.total, result=s.result
            )
            for s in skills(session, user.id)
        ],
        modules=[
            ModuleMedalOut(
                module_id=m.module_id,
                complete=m.complete,
                on_your_own=m.on_your_own,
                answered=m.answered,
                total=m.total,
                medal=m.medal,
                heading_for=m.heading_for,
                objectives=list(m.objectives),
            )
            for m in module_medals(session, user.id)
        ],
    )
