import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import GradingOutcome, RiskOrigin
from app.schemas.project import normalize_tags


class SuggestionQuery(BaseModel):
    title: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=5000)
    tags: list[str] = Field(default_factory=list)
    exclude_project_id: uuid.UUID | None = None
    limit: int = Field(default=10, ge=1, le=25)

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        return normalize_tags(v)


class SuggestionSource(BaseModel):
    risk_id: uuid.UUID
    project_id: uuid.UUID
    project_title: str
    project_similarity: float
    outcome: GradingOutcome
    mean_predicted_probability: float | None
    origin: RiskOrigin
    closed_at: datetime | None


class Suggestion(BaseModel):
    statement: str
    score: float
    materialization_rate: float
    occurrences: int
    mean_predicted_probability: float | None
    tags: list[str]
    sources: list[SuggestionSource]


class SuggestionsQueryEcho(BaseModel):
    tags: list[str]
    matched_projects: int


class SuggestionsOut(BaseModel):
    query: SuggestionsQueryEcho
    suggestions: list[Suggestion]
