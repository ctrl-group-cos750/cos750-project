"""The bonus quest offer (SE document FR-8.3)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Module
from app.schemas.quests import QuestOut
from app.services.attempts import bonus_quests
from app.services.modules import quest_open
from app.services.rewards import real_work_on


def offered_quests(session: Session, user_id: int) -> list[QuestOut]:
    """The bonus quests offered to this student: those they may open now (`modules.quest_open`:
    they have reached the quest's segment, or finished its module), in module order. A quest
    counts as completed only if they answered it right at the first attempt without hint 3 or 4
    (`rewards.real_work_on`), which is its only route to its points and badge."""
    quest_ids = bonus_quests(session)
    activities = list(
        session.scalars(
            select(Activity).where(Activity.id.in_(quest_ids), Activity.module_id.is_not(None))
        )
    )
    modules = {
        m.id: m
        for m in session.scalars(
            select(Module).where(Module.id.in_({a.module_id for a in activities}))
        )
    }
    completed = real_work_on(session, user_id, quest_ids)
    offered = [a for a in activities if a.module_id in modules and quest_open(session, user_id, a)]
    offered.sort(key=lambda a: (modules[a.module_id or 0].position, a.id))
    return [
        QuestOut(
            id=a.id,
            title=a.title,
            module_id=modules[a.module_id or 0].id,
            module_number=modules[a.module_id or 0].id,  # a module's id is its number
            module_title=modules[a.module_id or 0].title,
            completed=a.id in completed,
        )
        for a in offered
    ]
