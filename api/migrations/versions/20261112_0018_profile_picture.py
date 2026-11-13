"""profile_picture: a student can upload their own profile picture (FR-1.6), as well as choose one
of the team's. Three new columns on `users`, empty for everyone, so nothing changes for existing
students.

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("picture", sa.LargeBinary(), nullable=True))
        batch.add_column(sa.Column("picture_type", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("picture_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("picture_at")
        batch.drop_column("picture_type")
        batch.drop_column("picture")
