"""rewards: points rules and entries, earned badges, and the hide-rewards setting (FR-9)

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The SE document's points table (FR-9.1, FR-9.2), as confirmed by the ID document §7.2.
DEFAULT_RULES = {
    "activity_correct": 10,
    "activity_correct_supported": 4,
    "module_completed": 25,
    "objective_independent": 30,
    "objective_supported": 15,
    "bonus_quest": 20,
}


def upgrade() -> None:
    rules = op.create_table(
        "points_rules",
        sa.Column("event", sa.String(length=40), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("event"),
    )
    op.bulk_insert(rules, [{"event": e, "points": p} for e, p in DEFAULT_RULES.items()])

    op.create_table(
        "points_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(length=40), nullable=False),
        sa.Column("ref", sa.String(length=80), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "ref"),
    )
    op.create_index("ix_points_entries_user_id", "points_entries", ["user_id"])

    op.create_table(
        "user_badges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("badge", sa.String(length=40), nullable=False),
        sa.Column("ref", sa.String(length=40), server_default="", nullable=False),
        sa.Column("tier", sa.String(length=10), nullable=True),
        sa.Column(
            "awarded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("upgraded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "badge", "ref"),
    )
    op.create_index("ix_user_badges_user_id", "user_badges", ["user_id"])

    op.add_column(
        "users",
        sa.Column("hide_rewards", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "hide_rewards")
    op.drop_index("ix_user_badges_user_id", table_name="user_badges")
    op.drop_table("user_badges")
    op.drop_index("ix_points_entries_user_id", table_name="points_entries")
    op.drop_table("points_entries")
    op.drop_table("points_rules")
