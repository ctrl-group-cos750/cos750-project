"""modules, segments and module-progress: the course map and student progress tracking (FR-2)

Revision ID: 0009
Revises: 0006
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    legacy_tables = {"modules", "segments", "module_progress"}
    existing_tables = {table for table in legacy_tables if inspector.has_table(table)}
    has_video_segment = inspector.has_table("videos") and any(
        column["name"] == "segment_id" for column in inspector.get_columns("videos")
    )
    if existing_tables or has_video_segment:
        if existing_tables == legacy_tables and has_video_segment:
            return
        raise RuntimeError("The legacy modules migration is only partially present.")

    # 1. modules — no FKs to other new tables; must exist before segments.
    op.create_table(
        "modules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("goals", sa.Text(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. segments — references modules (just created) and videos/activities (exist since 0005/0004).
    #    videos.segment_id cannot be added here yet because segments does not exist yet; it is
    #    added after this table in step 3.
    op.create_table(
        "segments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("skip_check_activity_id", sa.Integer(), nullable=True),
        sa.Column("refresher_for", sa.String(), nullable=True),
        sa.Column("video_id", sa.Integer(), nullable=True),
        sa.Column("activity_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"]),
        sa.ForeignKeyConstraint(["skip_check_activity_id"], ["activities.id"]),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"]),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_segments_module_id"), "segments", ["module_id"])

    # 3. videos.segment_id — nullable FK back to segments (the other direction of the
    #    segments <-> videos bidirectional relationship; SE §8 ER diagram).
    #    Added as a separate step because segments must exist first.
    #    batch_alter_table is used so this also runs on SQLite (which the test suite uses).
    with op.batch_alter_table("videos") as batch_op:
        batch_op.add_column(sa.Column("segment_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_videos_segment_id_segments",
            "segments",
            ["segment_id"],
            ["id"],
        )

    # 4. module_progress — references users (since 0002) and modules (created above).
    op.create_table(
        "module_progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("module_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("current_segment_position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "module_id"),
    )
    op.create_index(op.f("ix_module_progress_user_id"), "module_progress", ["user_id"])
    op.create_index(op.f("ix_module_progress_module_id"), "module_progress", ["module_id"])


def downgrade() -> None:
    # Reverse of upgrade: drop in the opposite order, respecting FK dependencies.

    # 1. module_progress — drop first, no dependents.
    op.drop_index(op.f("ix_module_progress_module_id"), table_name="module_progress")
    op.drop_index(op.f("ix_module_progress_user_id"), table_name="module_progress")
    op.drop_table("module_progress")

    # 2. videos.segment_id — drop the FK constraint and column before dropping segments,
    #    because videos.segment_id references segments.id.
    #    batch_alter_table is used so this also runs on SQLite.
    with op.batch_alter_table("videos") as batch_op:
        batch_op.drop_constraint("fk_videos_segment_id_segments", type_="foreignkey")
        batch_op.drop_column("segment_id")

    # 3. segments — drop index then table; depends on modules, not the other way around.
    op.drop_index(op.f("ix_segments_module_id"), table_name="segments")
    op.drop_table("segments")

    # 4. modules — no remaining dependents.
    op.drop_table("modules")
