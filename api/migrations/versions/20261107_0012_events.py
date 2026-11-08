"""events: the pilot's timeline of what each student did, with when (FR-10.1, SE document §8)

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("ref", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_events_user_id"), "events", ["user_id"])
    op.create_index(op.f("ix_events_created_at"), "events", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_events_created_at"), table_name="events")
    op.drop_index(op.f("ix_events_user_id"), table_name="events")
    op.drop_table("events")
