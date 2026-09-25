import uuid

from pydantic import BaseModel


class UserRef(BaseModel):
    id: uuid.UUID
    email: str
    name: str


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None
