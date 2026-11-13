"""The student's own profile (FR-1.5, FR-1.6): the picture they chose and changing their password."""

from typing import Annotated, Literal

from pydantic import Field

from app.schemas.auth import Password
from app.schemas.base import ApiModel

# The set of profile pictures (FR-1.6), drawn by web/src/components/Avatar.tsx. Graph and BFS
# shapes, so none looks like a person and none says anything about who the student is.
Avatar = Literal["vertex", "edge", "path", "cycle", "tree", "star", "grid", "queue"]


class AvatarIn(ApiModel):
    """The picture to show, or null for the student's initial."""

    avatar: Avatar | None


# A 256 px square is at most about 200 kB as a PNG; its base64 is a third longer, plus the prefix.
PICTURE_MAX_BYTES = 200_000


class PictureIn(ApiModel):
    """An uploaded profile picture as a data URL ("data:image/png;base64,…"): JSON like every other
    request that changes something (NFR-S6), so a form on another site can't send one."""

    image: Annotated[str, Field(max_length=PICTURE_MAX_BYTES * 4 // 3 + 64)]


class PasswordChangeIn(ApiModel):
    current_password: Password
    new_password: Password


class ErrorOut(ApiModel):
    """An error the client shows as it is: `detail` says what went wrong, in plain words."""

    detail: str
