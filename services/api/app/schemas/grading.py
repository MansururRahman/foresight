import uuid

from pydantic import BaseModel, Field, field_validator

from app.models.enums import GradingOutcome
from app.schemas.project import ProjectOut, normalize_tags
from app.schemas.risk import GradingOut, RiskOut, _clean_statement
from app.schemas.session import SessionOut

__all__ = [
    "CloseoutOut",
    "GradingIn",
    "GradingOut",
    "GradingsPut",
    "PossibleDuplicate",
    "ProjectReport",
    "ReportRisk",
    "ReportSummary",
    "ReportSurprise",
    "SurpriseCreate",
]


class GradingIn(BaseModel):
    risk_id: uuid.UUID
    outcome: GradingOutcome
    note: str = Field(default="", max_length=2000)


class GradingsPut(BaseModel):
    gradings: list[GradingIn] = Field(min_length=1, max_length=500)


class SurpriseCreate(BaseModel):
    statement: str = Field(min_length=3, max_length=500)
    tags: list[str] = Field(default_factory=list)

    @field_validator("statement")
    @classmethod
    def _statement(cls, v: str) -> str:
        return _clean_statement(v)

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        return normalize_tags(v)


class PossibleDuplicate(BaseModel):
    surprise_id: uuid.UUID
    risk_id: uuid.UUID
    similarity: float


class CloseoutOut(BaseModel):
    project: ProjectOut
    session: SessionOut | None
    risks: list[RiskOut]
    surprises: list[RiskOut]
    ungraded_count: int
    possible_duplicates: list[PossibleDuplicate]


class ReportSummary(BaseModel):
    n_canonical: int
    n_graded: int
    n_voters: int
    expected_materialized: float
    actual_materialized: float
    project_brier: float | None
    n_predictions: int


class ReportRisk(BaseModel):
    risk_id: uuid.UUID
    statement: str
    tags: list[str]
    mean_predicted: float | None
    agreement: float | None
    mean_impact: float | None
    outcome: GradingOutcome | None
    miss: float | None
    note: str


class ReportSurprise(BaseModel):
    risk_id: uuid.UUID
    statement: str
    tags: list[str]


class ProjectReport(BaseModel):
    project: ProjectOut
    session: SessionOut | None
    summary: ReportSummary
    risks: list[ReportRisk]
    surprises: list[ReportSurprise]
    biggest_misses: list[ReportRisk]
