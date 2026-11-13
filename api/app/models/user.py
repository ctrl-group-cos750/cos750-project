from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# Demo accounts (FR-1.4, app/seed/demo_accounts.py) use this domain, and nobody can register with
# it, so a seeded account can never be a real student's. example.com is reserved (RFC 2606) but,
# unlike .invalid or .test, passes the email validation on the login form.
DEMO_EMAIL_DOMAIN = "demo.example.com"


class User(Base):
    """A student or a team member (SE document §8, FR-1). Only what POPIA lets us keep (NFR-S8)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Stored lowercased, so "A@b.co" and "a@b.co" are the same account.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(50))
    password_hash: Mapped[str] = mapped_column(String(255))
    # Team members: may export evaluation data (FR-10).
    is_staff: Mapped[bool] = mapped_column(default=False, server_default=false())
    # A seeded demo account (FR-1.4). Rebuilt on every seed, and left out of the evaluation data
    # (FR-10), so a demo or a rehearsal never counts as a student's results.
    is_demo: Mapped[bool] = mapped_column(default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Every session token carries this number. Logging out adds one, so every token issued before
    # stops working at once, even a copy someone took of the cookie.
    session_version: Mapped[int] = mapped_column(default=0, server_default="0")
    # The student chose to hide points and badges (FR-9.5). They are still earned, so turning them
    # back on shows everything; the mastery report is never hidden.
    hide_rewards: Mapped[bool] = mapped_column(default=False, server_default=false())
    # The profile picture the student chose from the team's set (FR-1.6): an id from
    # app/schemas/profile.py, drawn by web/src/components/Avatar.tsx. None shows their initial.
    avatar: Mapped[str | None] = mapped_column(String(20))
    # A picture the student uploaded instead (FR-1.6): a square image of at most 256 px, made in
    # their browser (which drops the photo's metadata) and checked to be a PNG, JPEG or WebP here.
    # Personal information under POPIA, so only they can fetch it (GET /api/me/picture), removing it
    # deletes it, and it goes with the account. Deferred: loaded only when the image is asked for.
    picture: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    picture_type: Mapped[str | None] = mapped_column(String(20))
    # When it was uploaded: part of its URL, so a new picture is never an old cached one.
    picture_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def picture_url(self) -> str | None:
        if self.picture_at is None:
            return None
        return f"/api/me/picture?v={int(self.picture_at.timestamp())}"
