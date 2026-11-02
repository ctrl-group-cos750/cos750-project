from datetime import datetime

from sqlalchemy import DateTime, String, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
