"""The student's own profile (FR-1.5, FR-1.6): the picture they chose and changing their password."""

from typing import Literal

from app.schemas.auth import Password
from app.schemas.base import ApiModel

# The set of profile pictures (FR-1.6), drawn by web/src/components/Avatar.tsx. Graph and BFS
# shapes, so none looks like a person and none says anything about who the student is.
Avatar = Literal["vertex", "edge", "path", "cycle", "tree", "star", "grid", "queue"]


class AvatarIn(ApiModel):
    """The picture to show, or null for the student's initial."""

    avatar: Avatar | None


class PasswordChangeIn(ApiModel):
    current_password: Password
    new_password: Password


class ErrorOut(ApiModel):
    """An error the client shows as it is: `detail` says what went wrong, in plain words."""

    detail: str
