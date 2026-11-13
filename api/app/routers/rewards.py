from typing import cast

from fastapi import APIRouter

from app.auth import CurrentUser
from app.db import DbSession
from app.models import User
from app.schemas.rewards import EarnedBadgeOut, RewardsOut, RewardsSettingsIn
from app.services.attempts import bonus_quests
from app.services.rewards import Tier, badges_of, mark_seen, set_hide_rewards, total_points

router = APIRouter(prefix="/api/rewards", tags=["rewards"])


def _rewards(session: DbSession, user: User) -> RewardsOut:
    quests = {str(quest): n for n, quest in enumerate(bonus_quests(session), start=1)}
    return RewardsOut(
        hide_rewards=user.hide_rewards,
        points=total_points(session, user.id),
        badges=[
            EarnedBadgeOut(
                badge=b.badge,
                ref=b.ref,
                tier=cast(Tier | None, b.tier),
                awarded_at=b.awarded_at,
                upgraded_at=b.upgraded_at,
                seen=b.seen_at is not None,
                quest_number=quests.get(b.ref) if b.badge == "quest" else None,
            )
            for b in badges_of(session, user.id)
        ],
    )


@router.get("")
def get_rewards(user: CurrentUser, session: DbSession) -> RewardsOut:
    """The logged-in student's points total and badges (FR-9.4: private to them). Points come from
    the server-side rules table and are never negative; badges are never taken away."""
    return _rewards(session, user)


@router.post("/seen")
def mark_rewards_seen(user: CurrentUser, session: DbSession) -> RewardsOut:
    """The app has announced every new badge, so none is announced twice."""
    mark_seen(session, user.id)
    session.commit()
    return _rewards(session, user)


@router.put("/settings")
def update_rewards_settings(
    body: RewardsSettingsIn, user: CurrentUser, session: DbSession
) -> RewardsOut:
    """Hide or show points and badges (FR-9.5). They are still earned while hidden, and the
    mastery report is never hidden."""
    set_hide_rewards(session, user, body.hide_rewards)
    session.commit()
    return _rewards(session, user)
