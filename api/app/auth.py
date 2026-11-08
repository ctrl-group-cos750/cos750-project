from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status

from app.db import DbSession
from app.models import User
from app.security import SESSION_COOKIE, read_session_token

SessionCookie = Annotated[str | None, Cookie(alias=SESSION_COOKIE)]


def session_user(session: DbSession, token: str | None) -> User | None:
    """The user a session cookie belongs to, if the token is valid and not logged out since."""
    claims = read_session_token(token) if token else None
    if claims is None:
        return None
    user_id, version = claims
    user = session.get(User, user_id)
    if user is None or user.session_version != version:
        return None
    return user


def get_current_user(session: DbSession, token: SessionCookie = None) -> User:
    user = session_user(session, token)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Log in to continue.")
    return user


# Use in a route as `user: CurrentUser`. Scope every query to `user.id` (NFR-S2, FR-1.3).
CurrentUser = Annotated[User, Depends(get_current_user)]


def get_staff_user(user: CurrentUser) -> User:
    """Team members only (`users.is_staff`). Granted on the staff portal's "Staff members" page,
    or with `python -m app.staff grant <email>` for the first one."""
    if not user.is_staff:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only team members can do this.")
    return user


# Use in a staff route as `staff: StaffUser`.
StaffUser = Annotated[User, Depends(get_staff_user)]
