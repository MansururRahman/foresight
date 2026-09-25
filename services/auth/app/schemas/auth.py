import re
import uuid
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not _EMAIL_RE.match(value):
        raise ValueError("value is not a valid email address")
    return value


# Lenient on purpose: special-use domains such as demo.local must be accepted.
Email = Annotated[str, AfterValidator(_validate_email)]


class RegisterIn(BaseModel):
    email: Email
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
