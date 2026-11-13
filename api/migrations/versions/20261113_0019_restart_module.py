"""restart_module: a student can restart a module to redo its questions (#restart). Three new
columns on `module_progress` (when it was last restarted, the newest attempt id then, and how many
times), and two on `hint_views`: a `round`, so a restarted module shows its hints again from level
1 (each level is still recorded once, but once per round), and `after_attempt`, the newest attempt
id when the hint was shown, so hint 3 or 4 only counts against the answers after it (#211 review).
Existing rows are round 0 and never restarted, so nothing changes for anyone until they restart;
existing hint views get the newest attempt of that student's at or before the hint's time.

The downgrade refuses while any hint view of a later round exists, rather than deleting it: those
rows are evaluation data (FR-10), and the old unique constraint can't hold them.

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
        batch.add_column(
            sa.Column("after_attempt", sa.Integer(), server_default="0", nullable=False)
        )
        batch.drop_constraint("hint_views_user_id_activity_id_level_key", type_="unique")
        batch.create_unique_constraint(
            "hint_views_user_id_activity_id_level_round_key",
            ["user_id", "activity_id", "level", "round"],
        )
    # Before this, a hint was only refused after a right answer (#158), so the student's newest
    # attempt by the hint's time is the boundary: their attempts after it came after the hint.
    op.execute(
        sa.text(
            "UPDATE hint_views SET after_attempt = COALESCE(("
            "SELECT MAX(attempts.id) FROM attempts"
            " WHERE attempts.user_id = hint_views.user_id"
            " AND attempts.created_at <= hint_views.created_at), 0)"
        )
    )


def downgrade() -> None:
    later = op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM hint_views WHERE round > 0"))
    if later:
        raise RuntimeError(
            f"{later} hint views are from a restarted module (round > 0). They are evaluation "
            "data and the old unique constraint can't hold them, so this downgrade won't delete "
            "them: export them (GET /api/staff/export/hints.csv), then delete them by hand to "
            "downgrade."
        )
    with op.batch_alter_table("hint_views") as batch:
        batch.drop_constraint("hint_views_user_id_activity_id_level_round_key", type_="unique")
        batch.create_unique_constraint(
            "hint_views_user_id_activity_id_level_key", ["user_id", "activity_id", "level"]
        )
        batch.drop_column("after_attempt")
        batch.drop_column("round")
    with op.batch_alter_table("module_progress") as batch:
        batch.drop_column("restarts")
        batch.drop_column("restarted_after_attempt")
        batch.drop_column("restarted_at")
