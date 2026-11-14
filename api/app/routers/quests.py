"""The bonus quest offer (SE document FR-8.3).

GET /api/quests → list[QuestOut]: the optional quests this student may try now.

A quest is an ordinary activity (purpose `bonus`), so the student opens it, asks for hints and
answers it through ``/api/activities/{id}``, and finishing it earns its points and badge there
(app/services/rewards.py). Nothing here can be required: there is no endpoint to accept or decline
a quest, because declining is simply not opening it.
"""

from fastapi import APIRouter

from app.auth import CurrentUser
from app.db import DbSession
from app.schemas.quests import QuestOut
from app.services.quests import offered_quests

router = APIRouter(prefix="/api/quests", tags=["quests"])


@router.get("")
def list_quests(user: CurrentUser, session: DbSession) -> list[QuestOut]:
    """The bonus quests offered to the logged-in student: those they may open now (they have
    reached the quest's segment at the end of its module, or finished the module), in module
    order, each with whether they have finished it. Only ever the student's own (NFR-S2)."""
    return offered_quests(session, user.id)
