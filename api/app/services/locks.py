"""One student's writes, one at a time (#138).

A student's answers, hint requests and position saves each read what is stored, then insert:
"no points for this answer yet, so add them", "no progress row yet, so make one", "hint 2 is
next". Two requests at the same moment (a double-click) both read before either writes, so both
insert, and the second fails on a unique constraint (a 500) or, for hint views, which had no
constraint, both rows are kept. And an answer to a mastery item recomputes the student's results
under a row lock taken after the attempt's insert, which already holds a weaker lock on the same
row, so two of them deadlock.

So each of those requests takes this lock first, before it reads or writes anything else. It is a
row lock on the student's `users` row, held until the request's transaction ends: a second request
from the same student waits for the first to commit, then reads what it wrote. Requests from
different students never wait for each other. SQLite (the tests' default) ignores it, and runs one
writer at a time anyway.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def lock_student(session: Session, user_id: int) -> None:
    """Wait for, then hold until this transaction ends, the lock on this student's writes."""
    session.execute(select(User.id).where(User.id == user_id).with_for_update())
