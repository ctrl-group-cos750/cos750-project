"""module_progress: each student's place in each module, and which modules they have completed
(FR-2.5, FR-2.6)

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "module_progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_segment_position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "module_id"),
    )
    op.create_index("ix_module_progress_module_id", "module_progress", ["module_id"])
    op.create_index("ix_module_progress_user_id", "module_progress", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_module_progress_user_id", table_name="module_progress")
    op.drop_index("ix_module_progress_module_id", table_name="module_progress")
    op.drop_table("module_progress")
