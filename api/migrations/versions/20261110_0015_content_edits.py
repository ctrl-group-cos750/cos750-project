"""content_edits: content becomes editable in the staff portal. `edited_at` marks a row staff
changed, so the seed never writes over it; `segments_edited_at` marks a module (or an objective's
review path) whose list of segments staff changed.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EDITED = ("objectives", "modules", "activities", "graph_scenarios")
SEGMENT_HOMES = ("objectives", "modules")


def upgrade() -> None:
    for table in EDITED:
        op.add_column(table, sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True))
    for table in SEGMENT_HOMES:
        op.add_column(
            table, sa.Column("segments_edited_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    for table in SEGMENT_HOMES:
        op.drop_column(table, "segments_edited_at")
    for table in EDITED:
        op.drop_column(table, "edited_at")
