import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import ProjectStatus, SessionPhase
from app.schemas.common import UserRef

MAX_TAGS = 20
MAX_TAG_LEN = 40


def normalize_tags(tags: list[str]) -> list[str]:
    """Lowercase, trim, drop empties, dedupe preserving order; enforce limits."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in tags:
        tag = " ".join(raw.strip().lower().split())
        if not tag or tag in seen:
            continue
        if len(tag) > MAX_TAG_LEN:
            raise ValueError(f"tag longer than {MAX_TAG_LEN} characters: {tag[:20]}…")
        seen.add(tag)
        out.append(tag)
    if len(out) > MAX_TAGS:
        raise ValueError(f"at most {MAX_TAGS} tags are allowed")
    return out


class _DatesMixin(BaseModel):
    planned_start: date | None = None
    planned_end: date | None = None

    @model_validator(mode="after")
    def _check_order(self) -> "_DatesMixin":
        if (
            self.planned_start is not None
            and self.planned_end is not None
            and self.planned_end < self.planned_start
        ):
            raise ValueError("planned_end must not be before planned_start")
        return self


class ProjectCreate(_DatesMixin):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        return normalize_tags(v)

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title must not be blank")
        return v


class ProjectPatch(_DatesMixin):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    tags: list[str] | None = None

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else normalize_tags(v)


class SessionSummary(BaseModel):
    id: uuid.UUID
    phase: SessionPhase
    sealed_at: datetime | None
    fully_graded_at: datetime | None


class ProjectOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    description: str
    tags: list[str]
    planned_start: date | None
    planned_end: date | None
    status: ProjectStatus
    activated_at: datetime | None
    closed_at: datetime | None
    archived_at: datetime | None
    created_by: UserRef
    created_at: datetime
    updated_at: datetime
    session: SessionSummary | None


class ProjectPage(BaseModel):
    items: list[ProjectOut]
    next_cursor: str | None


class ProjectTransition(BaseModel):
    to: Literal["active", "closed"]


class TransitionWarning(BaseModel):
    code: str
    count: int


class TransitionResult(BaseModel):
    project: ProjectOut
    warnings: list[TransitionWarning]
