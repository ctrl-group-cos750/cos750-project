"""merge: integrate modules/segments/progress (0009) with demo-accounts/rewards (0007/0008)

Revision ID: 0010
Revises: 0008, 0009
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: tuple[str, str] = ("0008", "0009")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Older installs used revision 0007 for modules, so the new demo-account 0007
    # may already appear applied without having added this column.
    user_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    if "is_demo" not in user_columns:
        op.add_column(
            "users", sa.Column("is_demo", sa.Boolean(), server_default=sa.false(), nullable=False)
        )


def downgrade() -> None:
    pass
