"""One student's writes, one at a time (#138).

Answering, revealing a hint and saving a module position each read the student's rows, decide,
then insert (an attempt and its points, a hint view, a progress row). Two such requests from one
student at once, a double-click or two tabs, used to interleave: both inserted the same progress
or points row and one failed on the unique constraint (500), both revealed the same hint level,
or, in the mastery check, both inserted an attempt and then deadlocked on the student's row.

`lock_student` is the first statement of each of those writes. It takes `FOR NO KEY UPDATE` on
the student's `users` row and holds it until the transaction ends, so a second write by the same
student waits for the first to commit and then sees its rows. It is the weaker row lock on
purpose: inserting a row that references the student takes `FOR KEY SHARE` on the same row, which
`FOR NO KEY UPDATE` doesn't block, so other inserts (the event log, for one) never wait on it and
can't deadlock with it. Different students never wait for each other. SQLite (the tests' default
database) has no row locks and ignores it; the Postgres tests run the races for real.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def lock_student(session: Session, user_id: int) -> None:
    """Wait for, then hold until commit or rollback, this student's write lock."""
    session.execute(select(User.id).where(User.id == user_id).with_for_update(key_share=True))
