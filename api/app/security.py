"""Passwords, session tokens and the session cookie (SE document NFR-S1, NFR-S2, NFR-S6)."""

import logging
import os
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Response
from pwdlib import PasswordHash

logger = logging.getLogger(__name__)

# The __Host- prefix makes browsers refuse this cookie unless it is Secure, for "/" and set by this
# exact host, so no other *.ctrlacademy.co.za site can plant or overwrite a session here.
SESSION_COOKIE = "__Host-session"
SESSION_LIFETIME = timedelta(days=14)  # FR-1.2
_ALGORITHM = "HS256"


def _secret_key() -> str:
    key = os.environ.get("SECRET_KEY")
    if key:
        return key
    # Fine for local runs and tests. In a deployment it would log everyone out on every restart,
    # so Coolify sets SECRET_KEY per environment (NFR-S5).
    logger.warning("SECRET_KEY is not set: using a random key, sessions end when the API restarts")
    return secrets.token_urlsafe(32)


SECRET_KEY = _secret_key()

_password_hash = PasswordHash.recommended()  # Argon2id
# Verified against when the email is unknown, so a wrong email takes as long as a wrong password
# and response times don't reveal which emails have accounts.
_DUMMY_HASH = _password_hash.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _password_hash.verify(password, _DUMMY_HASH)
        return False
    return _password_hash.verify(password, password_hash)


def create_session_token(user_id: int, version: int, now: datetime | None = None) -> str:
    issued = now or datetime.now(UTC)
    claims = {"sub": str(user_id), "ver": version, "iat": issued, "exp": issued + SESSION_LIFETIME}
    return jwt.encode(claims, SECRET_KEY, algorithm=_ALGORITHM)


def read_session_token(token: str) -> tuple[int, int] | None:
    """The user ID and session version in a valid, unexpired token, or None."""
    try:
        claims = jwt.decode(
            token, SECRET_KEY, algorithms=[_ALGORITHM], options={"require": ["exp", "sub", "ver"]}
        )
        version = claims["ver"]
        if not isinstance(version, int):
            return None
        return int(claims["sub"]), version
    except (jwt.InvalidTokenError, ValueError):
        return None


def set_session_cookie(response: Response, user_id: int, version: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user_id, version),
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,  # page scripts can't read it
        secure=True,  # HTTPS only; browsers treat http://localhost as secure too
        samesite="lax",  # not sent on cross-site POSTs
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=True, samesite="lax")
