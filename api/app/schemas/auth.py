from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
)
from pydantic.alias_generators import to_camel

from app.passwords import password_problem
from app.schemas.text import NoHiddenCharacters


class ApiModel(BaseModel):
    """camelCase in JSON, snake_case in Python. Unknown fields are refused."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True, extra="forbid"
    )


# The rules (length included) are in app/passwords.py, so each failure gets its own message.
Password = Annotated[str, Field(max_length=128)]
DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=50),
    NoHiddenCharacters,
]


class RegisterIn(ApiModel):
    # Validated in this order, so the password check can see the email and the name.
    email: EmailStr
    display_name: DisplayName
    password: Password

    @field_validator("password")
    @classmethod
    def hard_to_guess(cls, password: str, info: ValidationInfo) -> str:
        problem = password_problem(
            password, str(info.data.get("email", "")), info.data.get("display_name", "")
        )
        if problem:
            raise ValueError(problem)
        return password


class LoginIn(ApiModel):
    email: EmailStr
    # No length rules here: a login only needs to say "wrong", never "too short".
    password: Annotated[str, Field(max_length=128)]


class UserOut(ApiModel):
    id: int
    email: str
    display_name: str
    is_staff: bool
