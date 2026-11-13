"""`python -m app.pilot_name <email> [<email> ...]`: the pseudonym the pilot's CSV files use for
each of these accounts (FR-10.3, app/services/pseudonym.py), for the one team member who joins the
pilot survey's participant codes to the data (docs/pilot/README.md).

Run on the server, in the api container, where the database and `PILOT_PSEUDONYM_KEY` are: having
both is what makes it staff only. The staff portal no longer shows pseudonyms, so the files can't
be traced back to names from it (#215 review). Prints one line per email, `<email>,<pseudonym>`,
or `<email>,no such account`; nothing is written.
"""

import argparse
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User
from app.services.pseudonym import pseudonym


def pilot_names(session: Session, emails: Sequence[str]) -> list[tuple[str, str | None]]:
    """Each email with its account's pseudonym, or None if there is no such account."""
    out: list[tuple[str, str | None]] = []
    for email in emails:
        user_id = session.scalar(select(User.id).where(func.lower(User.email) == email.lower()))
        out.append((email, pseudonym(user_id) if user_id is not None else None))
    return out


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.pilot_name", description=__doc__)
    parser.add_argument("emails", nargs="+", help="the pilot accounts' emails")
    args = parser.parse_args(argv)
    from app.db import SessionLocal  # here, so importing this module opens no database

    with SessionLocal() as session:
        for email, name in pilot_names(session, args.emails):
            print(f"{email},{name or 'no such account'}")


if __name__ == "__main__":
    main()
