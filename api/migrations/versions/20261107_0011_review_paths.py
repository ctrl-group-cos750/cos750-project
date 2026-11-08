"""review paths: a segment belongs to a module or to an objective's review path (FR-7.5)

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Batch mode, so SQLite (the tests) can change the column and add the constraints too.
    with op.batch_alter_table("segments") as batch:
        batch.alter_column("module_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("review_objective_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_segments_review_objective_id", "objectives", ["review_objective_id"], ["id"]
        )
        batch.create_index(
            op.f("ix_segments_review_objective_id"), ["review_objective_id"], unique=False
        )
        batch.create_check_constraint(
            "ck_segments_one_home", "(module_id IS NULL) <> (review_objective_id IS NULL)"
        )


def downgrade() -> None:
    # Review-path segments have no module, so they can't survive the column becoming required.
    # A video placed on one is kept, with no segment, as the seed does for a removed segment.
    op.execute(
        "UPDATE videos SET segment_id = NULL WHERE segment_id IN "
        "(SELECT id FROM segments WHERE review_objective_id IS NOT NULL)"
    )
    op.execute("DELETE FROM segments WHERE review_objective_id IS NOT NULL")
    with op.batch_alter_table("segments") as batch:
        batch.drop_constraint("ck_segments_one_home", type_="check")
        batch.drop_index(op.f("ix_segments_review_objective_id"))
        batch.drop_constraint("fk_segments_review_objective_id", type_="foreignkey")
        batch.drop_column("review_objective_id")
        batch.alter_column("module_id", existing_type=sa.Integer(), nullable=False)
