"""What the staff portal's "Accounts" pages get back: every account, and one account's progress.
Staff only (app/routers/staff_accounts.py)."""

from datetime import datetime

from app.schemas.base import ApiModel


class AccountSummary(ApiModel):
    """One row of the accounts list."""

    id: int
    email: str
    display_name: str
    is_staff: bool
    created_at: datetime
    # The latest answer or hint, or None if they have done nothing yet.
    last_active_at: datetime | None


class AccountStats(ApiModel):
    attempts: int
    correct_attempts: int
    # Distinct activities they answered, and how many of those they got right at least once.
    activities_tried: int
    activities_passed: int
    hints_viewed: int


class AccountVideo(ApiModel):
    """Progress through one video: checkpoints answered correctly, out of all its checkpoints."""

    id: int
    title: str
    checkpoints_passed: int
    checkpoints_total: int


class AccountAttempt(ApiModel):
    """One answer, for the recent-activity list."""

    id: int
    activity_title: str
    kind: str
    correct: bool
    hint_level: int
    created_at: datetime


class AccountDetail(AccountSummary):
    stats: AccountStats
    videos: list[AccountVideo]
    recent_attempts: list[AccountAttempt]
