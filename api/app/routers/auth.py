from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth import CurrentUser, SessionCookie, session_user
from app.db import DbSession
from app.models import User
from app.rate_limit import (
    client_ip,
    login_account_limiter,
    login_address_limiter,
    register_limiter,
)
from app.schemas.auth import LoginIn, RegisterIn, UserOut
from app.security import clear_session_cookie, hash_password, set_session_cookie, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

EMAIL_TAKEN = "An account with this email already exists."


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserOut)
def register(body: RegisterIn, request: Request, response: Response, session: DbSession) -> User:
    """Create an account and log straight in (FR-1.1)."""
    register_limiter.check(client_ip(request))
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
    set_session_cookie(response, user.id, user.session_version)
    return user


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, session: DbSession) -> User:
    email = body.email.lower()
    address = client_ip(request)
    login_address_limiter.check(address)
    login_account_limiter.check(f"{address} {email}")
    user = session.scalar(select(User).where(User.email == email))
    valid = verify_password(body.password, user.password_hash if user else None)
    if user is None or not valid:
        # One message for both cases, so the form never reveals which emails have accounts.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Email or password is incorrect.")
    set_session_cookie(response, user.id, user.session_version)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, session: DbSession, token: SessionCookie = None) -> None:
    """Ends the session everywhere: every token issued to this user stops working, including
    any copy of the cookie. Works without a valid session too, so logging out never fails."""
    user = session_user(session, token)
    if user is not None:
        user.session_version += 1
        session.commit()
    clear_session_cookie(response)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
