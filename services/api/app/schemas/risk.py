import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import GradingOutcome, RiskOrigin, SessionPhase
from app.schemas.common import UserRef
from app.schemas.project import normalize_tags


class GradingOut(BaseModel):
    outcome: GradingOutcome
    note: str
    graded_by: UserRef
    updated_at: datetime


class Aggregates(BaseModel):
    vote_count: int
    mean_probability: float
    median_probability: float
    probability_stddev: float
    agreement: float
    mean_impact: float
    risk_score: float


class MyVote(BaseModel):
    probability: int
    impact: int


class MergedFrom(BaseModel):
    id: uuid.UUID
    statement: str


class RiskOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID | None
    project_id: uuid.UUID
    statement: str
    tags: list[str]
    origin: RiskOrigin
    duplicate_of: uuid.UUID | None
    source_risk_id: uuid.UUID | None
    author: UserRef | None
    created_at: datetime
    updated_at: datetime
    aggregates: Aggregates | None
    merged_from: list[MergedFrom]
    my_vote: MyVote | None
    grading: GradingOut | None


def _clean_statement(value: str) -> str:
    value = " ".join(value.split())
    if len(value) < 3:
        raise ValueError("statement must be at least 3 characters")
    if len(value) > 500:
        raise ValueError("statement must be at most 500 characters")
    return value


class RiskCreate(BaseModel):
    statement: str = Field(min_length=3, max_length=500)

    @field_validator("statement")
    @classmethod
    def _statement(cls, v: str) -> str:
        return _clean_statement(v)


class RiskPatch(BaseModel):
    statement: str | None = Field(default=None, min_length=3, max_length=500)
    tags: list[str] | None = None
    duplicate_of: uuid.UUID | None = None

    @field_validator("statement")
    @classmethod
    def _statement(cls, v: str | None) -> str | None:
        return None if v is None else _clean_statement(v)

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else normalize_tags(v)


class RiskAdopt(BaseModel):
    source_risk_id: uuid.UUID
    statement: str | None = Field(default=None, min_length=3, max_length=500)
    tags: list[str] | None = None

    @field_validator("statement")
    @classmethod
    def _statement(cls, v: str | None) -> str | None:
        return None if v is None else _clean_statement(v)

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else normalize_tags(v)


class SubmissionCount(BaseModel):
    user: UserRef
    count: int


class RiskList(BaseModel):
    phase: SessionPhase
    items: list[RiskOut]
    submission_counts: list[SubmissionCount] | None = None
