"""videos, checkpoints, the hint ladder and attempts' hint level (FR-3, FR-4.4, FR-4.5)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "attempts", sa.Column("hint_level", sa.Integer(), server_default="0", nullable=False)
    )
    op.create_table(
        "hints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("activity_id", "level"),
    )
    op.create_index(op.f("ix_hints_activity_id"), "hints", ["activity_id"])
    op.create_table(
        "hint_views",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_hint_views_user_id"), "hint_views", ["user_id"])
    op.create_index(op.f("ix_hint_views_activity_id"), "hint_views", ["activity_id"])
    op.create_table(
        "videos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("media_path", sa.String(length=300), nullable=False),
        sa.Column("captions_path", sa.String(length=300), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "checkpoints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("at_seconds", sa.Double(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"]),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_checkpoints_video_id"), "checkpoints", ["video_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_checkpoints_video_id"), table_name="checkpoints")
    op.drop_table("checkpoints")
    op.drop_table("videos")
    op.drop_index(op.f("ix_hint_views_activity_id"), table_name="hint_views")
    op.drop_index(op.f("ix_hint_views_user_id"), table_name="hint_views")
    op.drop_table("hint_views")
    op.drop_index(op.f("ix_hints_activity_id"), table_name="hints")
    op.drop_table("hints")
    op.drop_column("attempts", "hint_level")
