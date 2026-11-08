from fastapi import APIRouter, HTTPException, Response, status

from app.auth import CurrentUser
from app.db import DbSession
from app.models import User
from app.passwords import password_problem
from app.rate_limit import RateLimiter
from app.schemas.auth import UserOut
from app.schemas.profile import AvatarIn, PasswordChangeIn
from app.security import hash_password, set_session_cookie, verify_password

router = APIRouter(prefix="/api/me", tags=["profile"])

WRONG_CURRENT = "Your current password is not right."
SAME_PASSWORD = "Choose a new password, not the one you have now."  # noqa: S105 (a message)

# Guessing the current password from a session someone left open: 10 tries a minute per account,
# the same as logging in.
password_change_limiter = RateLimiter(limit=10, window=60)


@router.put("/avatar", response_model=UserOut)
def set_avatar(body: AvatarIn, user: CurrentUser, session: DbSession) -> User:
    """Choose a profile picture from the team's set, or none (FR-1.6). Only the student sees it."""
    user.avatar = body.avatar
    session.commit()
    return user


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: PasswordChangeIn, user: CurrentUser, session: DbSession, response: Response
) -> Response:
    """Change the password (FR-1.5). The current one is required, so a session left open on a
    shared computer can't be used to take the account over; the new one must pass the same rules
    as registration (NFR-S1). Every other session is logged out, and this one carries on.

    400 with the reason if the current password is wrong or the new one breaks a rule; 429 after
    10 tries a minute."""
    password_change_limiter.check(f"user:{user.id}")
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=WRONG_CURRENT)
    if body.new_password == body.current_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=SAME_PASSWORD)
    problem = password_problem(body.new_password, user.email, user.display_name)
    if problem:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=problem)
    user.password_hash = hash_password(body.new_password)
    user.session_version += 1  # every other device's cookie stops working
    session.commit()
    set_session_cookie(response, user.id, user.session_version)  # ...but not this one
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
