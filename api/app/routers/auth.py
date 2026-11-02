from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth import CurrentUser
from app.db import DbSession
from app.models import User
from app.rate_limit import login_limiter, register_limiter
from app.schemas.auth import LoginIn, RegisterIn, UserOut
from app.security import clear_session_cookie, hash_password, set_session_cookie, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

EMAIL_TAKEN = "An account with this email already exists."


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserOut,
    dependencies=[Depends(register_limiter)],
)
def register(body: RegisterIn, response: Response, session: DbSession) -> User:
    """Create an account and log straight in (FR-1.1)."""
    email = body.email.lower()
    if session.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=EMAIL_TAKEN)
    user = User(
        email=email, display_name=body.display_name, password_hash=hash_password(body.password)
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:  # registered by a parallel request since the check above
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail=EMAIL_TAKEN) from None
    set_session_cookie(response, user.id)
    return user


@router.post("/login", response_model=UserOut, dependencies=[Depends(login_limiter)])
def login(body: LoginIn, response: Response, session: DbSession) -> User:
    user = session.scalar(select(User).where(User.email == body.email.lower()))
    valid = verify_password(body.password, user.password_hash if user else None)
    if user is None or not valid:
        # One message for both cases, so the form never reveals which emails have accounts.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Email or password is incorrect.")
    set_session_cookie(response, user.id)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    """Clears the cookie. Works without a valid session, so logging out never fails."""
    clear_session_cookie(response)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
