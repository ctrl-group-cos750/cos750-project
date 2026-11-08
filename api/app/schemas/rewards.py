from datetime import datetime
from typing import Literal

from app.schemas.base import ApiModel


class EarnedBadgeOut(ApiModel):
    """A badge the student holds. `badge` is a catalogue id (web/src/components/achievements.ts);
    `ref` tells repeatable badges apart (the bonus quest's id), "" otherwise. `seen` is false until
    the app has announced it; an upgrade from bronze to gold makes it unseen again."""

    badge: str
    ref: str
    tier: Literal["bronze", "gold"] | None
    awarded_at: datetime
    upgraded_at: datetime | None
    seen: bool


class RewardsOut(ApiModel):
    """The student's own points and badges, and whether they chose to hide them (FR-9.4, FR-9.5).
    Only ever the logged-in student's: there is no way to see anyone else's."""

    hide_rewards: bool
    points: int
    badges: list[EarnedBadgeOut]


class RewardsSettingsIn(ApiModel):
    hide_rewards: bool
