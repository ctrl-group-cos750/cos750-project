# Import every model module here, so Alembic's autogenerate sees all tables.
from app.db import Base
from app.models.activity import Activity, Attempt, Hint, HintView
from app.models.content import Module, Objective, ObjectiveResult, Segment
from app.models.event import Event
from app.models.graph import GraphScenario
from app.models.rewards import PointsEntry, PointsRule, UserBadge
from app.models.user import User
from app.models.video import Checkpoint, Video

__all__ = [
    "Activity",
    "Attempt",
    "Base",
    "Checkpoint",
    "Event",
    "GraphScenario",
    "Hint",
    "HintView",
    "Module",
    "Objective",
    "ObjectiveResult",
    "PointsEntry",
    "PointsRule",
    "Segment",
    "User",
    "UserBadge",
    "Video",
]
