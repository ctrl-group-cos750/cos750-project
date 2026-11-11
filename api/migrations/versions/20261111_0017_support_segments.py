"""support_segments: a module's segment can be support for one objective (#172, FR-8.4), shown only
to a student struggling with that objective in that module. `segments.support_for` names the
objective. `shown_segments` records each such segment the server has shown a student, so it stays
shown from then on even if a re-grade or a staff edit would decide differently later.

Both are new and empty for existing data: no segment is support until the fixtures say so, so every
existing student keeps exactly what they see and where they are.

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("segments") as batch:
        batch.add_column(sa.Column("support_for", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "segments_support_for_fkey", "objectives", ["support_for"], ["id"]
        )
    op.create_table(
        "shown_segments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "segment_id",
            sa.Integer(),
            sa.ForeignKey("segments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "shown_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "segment_id"),
    )
    op.create_index("ix_shown_segments_user_id", "shown_segments", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_shown_segments_user_id", table_name="shown_segments")
    op.drop_table("shown_segments")
    with op.batch_alter_table("segments") as batch:
        batch.drop_constraint("segments_support_for_fkey", type_="foreignkey")
        batch.drop_column("support_for")
