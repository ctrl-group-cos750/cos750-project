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
can't deadlock with it. Different students never wait for each other. Marking badges seen and
deleting an account take it too, so neither interleaves with an answer being recorded.

Lock order. An answer or hint first takes `FOR KEY SHARE` on its activity (`hold_activity`), then
the student. The seed, on a deploy, deletes unused activities (taking their rows) and then
recomputes students (taking theirs). Taken the other way round, an answer to an activity the seed
is deleting held the student while waiting for the activity, the seed held the activity while
waiting for the student, and Postgres killed one. In this order the answer waits without holding
the student, and once the seed commits it finds the activity gone (404). The seed's other writes
to activities are plain updates, which `FOR KEY SHARE` doesn't wait for.

SQLite (the tests' default database) has no row locks and ignores all this; the Postgres tests
run the races for real.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, User


class ActivityGone(LookupError):
    """The activity was deleted (by the seed, on a deploy) while this request was answering it."""


def lock_student(session: Session, user_id: int) -> None:
    """Wait for, then hold until commit or rollback, this student's write lock."""
    session.execute(select(User.id).where(User.id == user_id).with_for_update(key_share=True))


def hold_activity(session: Session, activity_id: int) -> None:
    """Take `FOR KEY SHARE` on the activity, before `lock_student` (see "Lock order" above), so it
    can't be deleted until this transaction ends. Raises `ActivityGone` if it already was."""
    held = session.scalar(
        select(Activity.id)
        .where(Activity.id == activity_id)
        .with_for_update(read=True, key_share=True)
    )
    if held is None:
        raise ActivityGone(activity_id)
