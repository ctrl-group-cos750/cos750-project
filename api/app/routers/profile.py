import base64
import binascii
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response, status

from app.auth import CurrentUser
from app.db import DbSession
from app.models import User
from app.passwords import password_problem
from app.rate_limit import RateLimiter
from app.schemas.auth import UserOut
from app.schemas.profile import (
    PICTURE_MAX_BYTES,
    AvatarIn,
    ErrorOut,
    PasswordChangeIn,
    PictureIn,
)
from app.security import hash_password, set_session_cookie, verify_password

router = APIRouter(prefix="/api/me", tags=["profile"])

WRONG_CURRENT = "Your current password is not right."
SAME_PASSWORD = "Choose a new password, not the one you have now."  # noqa: S105 (a message)

# Guessing the current password from a session someone left open: 10 tries a minute per account,
# the same as logging in.
password_change_limiter = RateLimiter(limit=10, window=60)


@router.put("/avatar", response_model=UserOut)
def set_avatar(body: AvatarIn, user: CurrentUser, session: DbSession) -> User:
    """Choose a profile picture from the team's set, or none (FR-1.6). Only the student sees it.
    An uploaded picture is deleted: the student has chosen something else."""
    user.avatar = body.avatar
    _forget_picture(user)
    session.commit()
    return user


NOT_A_PICTURE = "Choose a PNG, JPEG or WebP picture."
TOO_BIG = "The picture is too big. Choose a smaller one."
NO_PICTURE = "You have not uploaded a picture."
# The first bytes of each format we keep: what the file is, whatever it claims to be.
SIGNATURES = {
    "image/png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
    "image/webp": lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP",
}

# Ten uploads a minute per account is plenty for trying a few pictures.
picture_limiter = RateLimiter(limit=10, window=60)


def _forget_picture(user: User) -> None:
    user.picture = None
    user.picture_type = None
    user.picture_at = None


@router.put(
    "/picture",
    response_model=UserOut,
    responses={
        400: {"model": ErrorOut, "description": "Not a PNG, JPEG or WebP, or over 200 kB."},
        429: {"model": ErrorOut, "description": "More than 10 uploads in a minute."},
    },
)
def upload_picture(body: PictureIn, user: CurrentUser, session: DbSession) -> User:
    """Upload a profile picture of their own (FR-1.6), shown instead of the team's pictures.

    The browser makes it a small square first (which also drops a photo's location and camera
    details); the server keeps it only if its bytes really are a PNG, JPEG or WebP of at most
    200 kB. It is personal information (POPIA), so only the student can fetch it."""
    picture_limiter.check(f"user:{user.id}")
    header, _, data = body.image.partition(",")
    claimed = header.removeprefix("data:").removesuffix(";base64")
    if (
        not header.startswith("data:")
        or not header.endswith(";base64")
        or claimed not in SIGNATURES
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=NOT_A_PICTURE)
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=NOT_A_PICTURE) from None
    if len(raw) > PICTURE_MAX_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=TOO_BIG)
    if not SIGNATURES[claimed](raw):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=NOT_A_PICTURE)
    user.picture = raw
    user.picture_type = claimed
    user.picture_at = datetime.now(UTC)
    user.avatar = None
    session.commit()
    return user


@router.get(
    "/picture",
    response_class=Response,
    responses={
        200: {"content": {"image/png": {}, "image/jpeg": {}, "image/webp": {}}},
        404: {"model": ErrorOut, "description": "No picture uploaded."},
    },
)
def get_picture(user: CurrentUser) -> Response:
    """The student's own uploaded picture. Its URL changes with each upload (`?v=`), so the browser
    may keep it; never anyone else's, and never served as anything but an image."""
    if user.picture is None or user.picture_type is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NO_PICTURE)
    return Response(
        content=user.picture,
        media_type=user.picture_type,
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.delete("/picture", response_model=UserOut)
def delete_picture(user: CurrentUser, session: DbSession) -> User:
    """Delete the uploaded picture; the student's initial shows until they choose another."""
    _forget_picture(user)
    session.commit()
    return user


@router.post(
    "/password",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        400: {
            "model": ErrorOut,
            "description": "The current password is wrong, or the new one is the same or breaks "
            "a password rule. `detail` says which.",
        },
        429: {"model": ErrorOut, "description": "More than 10 tries in a minute."},
    },
)
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
