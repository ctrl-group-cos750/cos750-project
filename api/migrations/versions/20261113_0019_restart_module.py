"""restart_module: a student can restart a module to redo its questions (#restart). Two new columns
on `module_progress` (when it was last restarted, and how many times) and a `round` on
`hint_views`, so a restarted module shows its hints again from level 1: each level is still
recorded once, but once per round. Existing rows are round 0 and never restarted, so nothing
changes for anyone until they restart.

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("module_progress") as batch:
        batch.add_column(sa.Column("restarted_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("restarted_after_attempt", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("restarts", sa.Integer(), server_default="0", nullable=False))
    with op.batch_alter_table("hint_views") as batch:
        batch.add_column(sa.Column("round", sa.Integer(), server_default="0", nullable=False))
        batch.drop_constraint("hint_views_user_id_activity_id_level_key", type_="unique")
        batch.create_unique_constraint(
            "hint_views_user_id_activity_id_level_round_key",
            ["user_id", "activity_id", "level", "round"],
        )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM hint_views WHERE round > 0"))
    with op.batch_alter_table("hint_views") as batch:
        batch.drop_constraint("hint_views_user_id_activity_id_level_round_key", type_="unique")
        batch.create_unique_constraint(
            "hint_views_user_id_activity_id_level_key", ["user_id", "activity_id", "level"]
        )
        batch.drop_column("round")
    with op.batch_alter_table("module_progress") as batch:
        batch.drop_column("restarts")
        batch.drop_column("restarted_after_attempt")
        batch.drop_column("restarted_at")
