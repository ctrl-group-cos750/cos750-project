"""The bonus quest offer (SE document FR-8.3)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Module, ModuleProgress
from app.schemas.quests import QuestOut
from app.services.attempts import bonus_quests
from app.services.rewards import real_work


def offered_quests(session: Session, user_id: int) -> list[QuestOut]:
    """The bonus quests offered to this student: those after a module they have finished, in
    module order. A quest counts as completed only if they answered it correctly without hint 3 or
    4, which is its only route to its points and badge."""
    completed = set(
        session.scalars(
            select(ModuleProgress.module_id).where(
                ModuleProgress.user_id == user_id,
                ModuleProgress.status == "complete",
            )
        )
    )
    quest_ids = [activity_id for activity_id in bonus_quests(session) if activity_id]
    activities = {
        a.id: a
        for a in session.scalars(
            select(Activity).where(Activity.id.in_(quest_ids), Activity.module_id.is_not(None))
        )
    }
    modules = {
        m.id: m
        for m in session.scalars(
            select(Module).where(
                Module.id.in_({a.module_id for a in activities.values() if a.module_id is not None})
            )
        )
    }
    completed_quests = {
        activity_id
        for activity_id in quest_ids
        if session.scalar(
            select(Attempt.id)
            .where(
                Attempt.user_id == user_id,
                Attempt.activity_id == activity_id,
                Attempt.correct.is_(True),
                real_work(),
            )
            .limit(1)
        )
        is not None
    }
    out: list[QuestOut] = []
    for activity_id in quest_ids:
        activity = activities.get(activity_id)
        if activity is None or activity.module_id is None or activity.module_id not in completed:
            continue
        module = modules.get(activity.module_id)
        if module is None:
            continue
        out.append(
            QuestOut(
                id=activity.id,
                title=activity.title,
                module_id=module.id,
                module_number=module.id,
                module_title=module.title,
                completed=activity.id in completed_quests,
            )
        )
    return out
