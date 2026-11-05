"""Make a team member staff, so they can upload media and edit videos (`users.is_staff`).

    python -m app.staff grant ada@example.com
    python -m app.staff revoke ada@example.com
    python -m app.staff list

In Docker: `docker compose exec api python -m app.staff grant <email>`. On Coolify: the api
container's terminal. The account must exist first (register in the app).
"""

import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.models import User


def main(args: list[str]) -> int:
    with SessionLocal() as session:
        if args == ["list"]:
            for email in session.scalars(select(User.email).where(User.is_staff)):
                print(email)
            return 0
        if len(args) != 2 or args[0] not in {"grant", "revoke"}:
            print(__doc__)
            return 2
        user = session.scalar(select(User).where(User.email == args[1].strip().lower()))
        if user is None:
            print(f"No account for {args[1]}. Register it in the app first.")
            return 1
        user.is_staff = args[0] == "grant"
        session.commit()
        print(f"{user.email}: staff = {user.is_staff}")
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
