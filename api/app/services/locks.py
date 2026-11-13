"""One student's writes, one at a time (#138).

Answering, revealing a hint and saving a module position each read the student's rows, decide,
then insert (an attempt and its points, a hint view, a progress row). Two such requests from one
student at once, a double-click or two tabs, used to interleave: both inserted the same progress
or points row and one failed on the unique constraint (500), both revealed the same hint level,
or, in the mastery check, both inserted an attempt and then deadlocked on the student's row.

`lock_student` is the first statement of each of those writes (#163 put it there). It takes `FOR NO KEY UPDATE` on
the student's `users` row and holds it until the transaction ends, so a second write by the same
student waits for the first to commit and then sees its rows. It is the weaker row lock on
purpose: inserting a row that references the student takes `FOR KEY SHARE` on the same row, which
`FOR NO KEY UPDATE` doesn't block, so other inserts (the event log, for one) never wait on it and
can't deadlock with it. Different students never wait for each other. Marking badges seen and
deleting an account take it too, so neither interleaves with an answer being recorded.

A student deleted while their requests wait for this lock (staff deleting the account) leaves
nothing to lock: `lock_student` then raises `StudentGone`, which the API answers with 401, as it
would for any request after the deletion, instead of failing later on a foreign key.

Lock order against the seed. An answer or hint first takes `FOR KEY SHARE` on its activity
(`hold_activity`), then the student. On a deploy the seed's `retire_dropped_activities` deletes
each dropped activity nobody has used (taking its row), and later `recompute_all` takes students.
There are two orders in which they can meet:

- The seed deletes first. An answer to that activity used to hold the student while waiting for
  the activity, while the seed, holding the activity, waited for the student: a deadlock, and
  Postgres killed one. Now the answer waits holding nothing, and once the seed commits it finds
  the activity gone (`ActivityGone`, 404).
- The answer comes first. It holds the activity and inserts its attempt, not yet committed. The
  seed's "used?" check couldn't see that attempt, so it deleted the activity, waited for the
  answer and then failed on the foreign key, failing that seed run. The seed now locks each
  dropped activity `FOR UPDATE` before the check (`retire_dropped_activities`), so it waits for
  the answer, sees its attempt, and only hides the activity.

Both are tested deterministically in tests/test_concurrency.py.

The seed's other writes to activities are plain updates, which `FOR KEY SHARE` doesn't wait for,
so an ordinary deploy holds up no answers.

SQLite (the tests' default database) has no row locks and ignores all this; the Postgres tests
run the races for real.
"""

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Activity, User


class StudentGone(LookupError):
    """The student's account was deleted while this request waited for their lock."""


class ActivityGone(LookupError):
    """The activity was deleted (by the seed, on a deploy) while this request was answering it."""


def lock_student(session: Session, user_id: int) -> None:
    """Wait for, then hold until commit or rollback, this student's write lock. Raises
    `StudentGone` if the account no longer exists (deleted while this request waited)."""
    held = session.scalar(select(User.id).where(User.id == user_id).with_for_update(key_share=True))
    if held is None:
        raise StudentGone(user_id)


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


def claim_writes(session: Session) -> None:
    """On SQLite only (the tests' and the local end-to-end runs' database): start this
    transaction's write now, with a statement that changes nothing, so a second request that
    would make the same decision waits for this one to commit and then reads what it wrote.
    SQLite has no row locks for `lock_student` to take, and it starts a write transaction only at
    the first write, so two requests could both read "not yet" and both write. One database write
    at a time is how SQLite works anyway; this only moves the start earlier, so use it for a short
    request that must not run twice (the quick check, app/services/quick_check.py). On Postgres it
    does nothing: `lock_student` covers it."""
    if session.get_bind().dialect.name == "sqlite":
        session.execute(text("UPDATE users SET id = id WHERE 0"))
