"""A student's own history: every row that belongs to them, for deleting it all at once.

Used by the staff portal's account delete (POPIA: nothing is kept about a deleted student) and by
the demo-account reset. Found from the models rather than listed, so a table added later
(points, badges, mastery, events) is cleared without anyone remembering to add it here. The
convention: a student's history points at them with `user_id`. Anything else pointing at users
(say, the staff member who made some content) is named otherwise and is never deleted.
"""

from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db import Base


def history_tables() -> list[tuple[Any, Any]]:
    """Every table holding a student's own history, children first, with its `user_id` column."""
    found = []
    for table in reversed(Base.metadata.sorted_tables):
        for fk in table.foreign_keys:
            if fk.column.table.name == "users" and fk.parent.name == "user_id":
                found.append((table, fk.parent))
    return found


def delete_history(session: Session, user_id: int) -> None:
    """Delete every row of this student's history (not committed). The user row itself stays."""
    for table, column in history_tables():
        session.execute(delete(table).where(column == user_id))
