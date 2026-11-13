from typing import Literal

from app.schemas.base import ApiModel
from app.schemas.mastery import ObjectiveState

Medal = Literal["gold", "silver", "bronze"]


class SkillOut(ApiModel):
    """One objective on the skill profile (FR-9.7). `correct` of `total` is practice progress:
    the objective's practice items answered correctly. `result` is the mastery result once the
    mastery check (or a review path) has decided it, else null."""

    id: int
    text: str
    correct: int
    total: int
    result: ObjectiveState | None


class ModuleMedalOut(ApiModel):
    """A module's medal (FR-9.8): `medal` once the module is complete (gold, every activity
    answered right without hint 3 or 4; silver, at least half; bronze, finished), and
    `headingFor`, what the answers so far are on course for. Never counts attempts or time.
    `objectives` are the learning objectives its activities practise."""

    module_id: int
    complete: bool
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
