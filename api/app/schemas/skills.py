from typing import Literal

from app.schemas.base import ApiModel
from app.schemas.mastery import ObjectiveState

Medal = Literal["gold", "silver", "finished"]


class ImproveOut(ApiModel):
    """Where the student can work on an objective (#214): `practise` in a module (at `segment`,
    0-based, when they can open it there), `revisit` a module (secure in practice, or met with
    support), its `review` path once module 6 has said "not yet" (FR-7.5), or the mastery `check`
    (module 6) once practice can no longer make it secure: too many first answers weren't on your
    own, and only a first attempt counts (FR-9.6). Never module 6 to practise. `locked`: the
    module isn't open to the student yet (the mastery check, before modules 1 to 5 are done), so
    the profile says where it will be shown rather than linking to a locked page."""

    kind: Literal["practise", "revisit", "review", "check"]
    module_id: int | None
    segment: int | None
    objective_id: int | None
    locked: bool = False


class SkillOut(ApiModel):
    """One objective on the skill profile (FR-9.7). `level` is practice progress in three coarse
    steps (not started, practising, secure: every practice item answered and at least 80% right
    without hint 3 or 4); the counts are the evidence behind it, of `total` practice items.
    `result` is the mastery result once the mastery check (or a review path) has decided it;
    `improve`, where to work on it next (none once met on your own). `modules` are the modules, in
    course order, whose segments hold its practice questions: where its badge's first level,
    Practised, is earned."""

    id: int
    text: str
    answered: int
    correct: int
    on_your_own: int
    total: int
    level: Literal["not_started", "practising", "secure"]
    result: ObjectiveState | None
    improve: ImproveOut | None
    modules: list[int]


class ModuleMedalOut(ApiModel):
    """A module's medal (FR-9.8): `medal` once the module is complete (gold, every activity right
    at the first attempt without a hint; silver, right at the first attempt without hint 3 or 4;
    finished, the module finished with at least one right at the first attempt without hint 3 or
    4: not "bronze", which is an objective badge's level),
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
