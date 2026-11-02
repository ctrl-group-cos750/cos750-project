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
