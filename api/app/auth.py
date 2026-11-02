from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status

from app.db import DbSession
from app.models import User
from app.security import SESSION_COOKIE, read_session_token


def get_current_user(
    session: DbSession,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    user_id = read_session_token(token) if token else None
    user = session.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Log in to continue.")
    return user


# Use in a route as `user: CurrentUser`. Scope every query to `user.id` (NFR-S2, FR-1.3).
CurrentUser = Annotated[User, Depends(get_current_user)]
