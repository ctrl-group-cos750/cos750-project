"""Pydantic schemas for the bonus quest offer (SE document FR-8.3)."""

from app.schemas.base import ApiModel


class QuestOut(ApiModel):
    """One bonus quest offered to the student: an optional extra challenge after a module they
    have completed. The quest is an ordinary activity, so it is opened, hinted and answered
    through ``/api/activities/{id}``; ``id`` is that activity's id. ``completed`` is true once
    they have answered it correctly without hint 3 or 4, which is what earns its points and
    badge."""

    id: int
    title: str
    module_id: int
    module_number: int
    module_title: str
    completed: bool
