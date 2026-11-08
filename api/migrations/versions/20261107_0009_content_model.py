"""content model: objectives, modules and segments; activities tagged with their module,
objective and purpose; videos placed in a segment (FR-2, FR-4.3, SE document §8)

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "objectives",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("bloom_level", sa.String(length=100), nullable=False),
        sa.Column("criterion", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "modules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("goals", sa.JSON(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "segments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), server_default="", nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=True),
        sa.Column("skip_check_activity_id", sa.Integer(), nullable=True),
        sa.Column("refresher_for", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"]),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"]),
        sa.ForeignKeyConstraint(["skip_check_activity_id"], ["activities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_segments_module_id"), "segments", ["module_id"])

    # Batch mode, so SQLite (the tests) can add the foreign keys too: it rebuilds the table.
    with op.batch_alter_table("activities") as batch:
        batch.add_column(sa.Column("module_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("objective_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("purpose", sa.String(length=32), server_default="practice", nullable=False)
        )
        batch.create_foreign_key("fk_activities_module_id", "modules", ["module_id"], ["id"])
        batch.create_foreign_key(
            "fk_activities_objective_id", "objectives", ["objective_id"], ["id"]
        )
        batch.create_index(op.f("ix_activities_module_id"), ["module_id"])
        batch.create_index(op.f("ix_activities_objective_id"), ["objective_id"])

    with op.batch_alter_table("videos") as batch:
        batch.add_column(sa.Column("segment_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_videos_segment_id", "segments", ["segment_id"], ["id"])
        batch.create_unique_constraint("uq_videos_segment_id", ["segment_id"])


def downgrade() -> None:
    with op.batch_alter_table("videos") as batch:
        batch.drop_constraint("uq_videos_segment_id", type_="unique")
        batch.drop_constraint("fk_videos_segment_id", type_="foreignkey")
        batch.drop_column("segment_id")
    with op.batch_alter_table("activities") as batch:
        batch.drop_index(op.f("ix_activities_objective_id"))
        batch.drop_index(op.f("ix_activities_module_id"))
        batch.drop_constraint("fk_activities_objective_id", type_="foreignkey")
        batch.drop_constraint("fk_activities_module_id", type_="foreignkey")
        batch.drop_column("purpose")
        batch.drop_column("objective_id")
        batch.drop_column("module_id")
    op.drop_index(op.f("ix_segments_module_id"), table_name="segments")
    op.drop_table("segments")
    op.drop_table("modules")
    op.drop_table("objectives")
