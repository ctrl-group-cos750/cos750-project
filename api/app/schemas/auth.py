from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints
from pydantic.alias_generators import to_camel

from app.schemas.text import NoHiddenCharacters


class ApiModel(BaseModel):
    """camelCase in JSON, snake_case in Python. Unknown fields are refused."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True, extra="forbid"
    )


Password = Annotated[str, Field(min_length=8, max_length=128)]
DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=50),
    NoHiddenCharacters,
]


class RegisterIn(ApiModel):
    email: EmailStr
    password: Password
    display_name: DisplayName


class LoginIn(ApiModel):
    email: EmailStr
    # No length rules here: a login only needs to say "wrong", never "too short".
    password: Annotated[str, Field(max_length=128)]


class UserOut(ApiModel):
    id: int
    email: str
    display_name: str
    is_staff: bool
