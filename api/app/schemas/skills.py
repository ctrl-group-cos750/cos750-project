from typing import Literal

from app.schemas.base import ApiModel
from app.schemas.mastery import ObjectiveState

Medal = Literal["gold", "silver", "bronze"]


class SkillOut(ApiModel):
    """One objective on the skill profile (FR-9.7). `level` is practice progress in three coarse
    steps (not started, practising, secure: every practice item answered and at least 80% right
    on your own, the first answer right before hint 3 or 4); the counts are the evidence behind
    it, of `total` practice items.
    `result` is the mastery result once the mastery check (or a review path) has decided it."""

    id: int
    text: str
    answered: int
    correct: int
    on_your_own: int
    total: int
    level: Literal["not_started", "practising", "secure"]
    result: ObjectiveState | None


class ModuleMedalOut(ApiModel):
    """A module's medal (FR-9.8): `medal` once the module is complete (gold, every first answer
    right without a hint; silver, every first answer right without hint 3 or 4; bronze, finished),
    and `headingFor`, what the answers so far are on course for. Never counts time or speed.
    `objectives` are the learning objectives its activities practise."""

    module_id: int
    complete: bool
    first_time: int
    on_your_own: int
    answered: int
    total: int
    medal: Medal | None
    heading_for: Medal | None
    objectives: list[int]


class SkillsOut(ApiModel):
    """The logged-in student's skill profile and module medals. Only ever their own."""

    objectives: list[SkillOut]
    modules: list[ModuleMedalOut]
