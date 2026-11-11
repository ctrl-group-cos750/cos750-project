"""hint_view_once: a student is shown each hint level of an activity once. Two hint requests at the
same moment used to record the same level twice (#138), which inflated the pilot's hint counts. The
duplicates already stored are removed first, keeping each level's earliest view.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM hint_views WHERE id NOT IN ("
            " SELECT MIN(id) FROM hint_views GROUP BY user_id, activity_id, level)"
        )
    )
    with op.batch_alter_table("hint_views") as batch:
        batch.create_unique_constraint(
            "hint_views_user_id_activity_id_level_key", ["user_id", "activity_id", "level"]
        )


def downgrade() -> None:
    with op.batch_alter_table("hint_views") as batch:
        batch.drop_constraint("hint_views_user_id_activity_id_level_key", type_="unique")
