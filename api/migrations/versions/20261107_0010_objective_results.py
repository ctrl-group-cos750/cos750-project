"""mastery: each objective's rule as the mastery service evaluates it, and each student's result
per objective (FR-7, SE document §8)

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable: the rows already there get their rule on the next seed, which runs on every start.
    with op.batch_alter_table("objectives") as batch:
        batch.add_column(sa.Column("pass_fraction", sa.Double(), nullable=True))
        batch.add_column(sa.Column("max_wrong", sa.Integer(), nullable=True))
    op.create_table(
        "objective_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("objective_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["objective_id"], ["objectives.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "objective_id"),
    )
    op.create_index(op.f("ix_objective_results_user_id"), "objective_results", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_objective_results_user_id"), table_name="objective_results")
    op.drop_table("objective_results")
    with op.batch_alter_table("objectives") as batch:
        batch.drop_column("max_wrong")
        batch.drop_column("pass_fraction")
