import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.enums import GradingOutcome
from app.schemas.common import UserRef

BiasLabel = Literal["over_estimates_risk", "under_estimates_risk", "calibrated"]
ConfidenceLabel = Literal["overconfident", "underconfident", "calibrated"]
TrendDirection = Literal["improving", "worsening", "flat", "insufficient_data"]


class Bin(BaseModel):
    index: int
    range: tuple[int, int]
    n: int
    mean_predicted: float | None
    observed: float | None
    reliable: bool


class TrendPoint(BaseModel):
    project_id: uuid.UUID
    project_title: str | None
    closed_at: datetime | None
    n_project: int
    brier_project: float
    n_rolling: int
    brier_rolling: float | None
    brier_cumulative: float


class Trend(BaseModel):
    direction: TrendDirection
    slope: float | None
    points: list[TrendPoint]


class Sample(BaseModel):
    n_graded: int
    n_projects: int
    needed: int
    sufficient: bool


class _SummaryFields(BaseModel):
    brier: float | None
    brier_skill: float | None
    base_rate: float
    bias: float | None
    bias_label: BiasLabel | None
    ece: float | None
    overconfidence: float | None
    confidence_label: ConfidenceLabel | None
    bins: list[Bin]
    trend: Trend


class CalibrationSummary(_SummaryFields):
    sample: Sample


class WorstCall(BaseModel):
    risk_id: uuid.UUID
    project_id: uuid.UUID
    project_title: str | None
    statement: str | None
    probability: int
    outcome: GradingOutcome
    brier_contribution: float


class UserCalibration(CalibrationSummary):
    user: UserRef
    workspace_id: uuid.UUID
    worst_calls: list[WorstCall]


class WorkspaceSample(BaseModel):
    n_graded: int
    n_projects_closed: int
    n_projects_graded: int
    n_voters: int
    needed: int
    sufficient: bool


class BlindSpot(BaseModel):
    risk_id: uuid.UUID
    project_id: uuid.UUID
    project_title: str
    statement: str
    tags: list[str]
    mean_predicted: float
    outcome: GradingOutcome
    miss: float


class TagCalibration(BaseModel):
    tag: str
    n: int
    mean_predicted: float
    observed: float
    bias: float
    brier: float
    chronic: Literal["under", "over"] | None


class RecentSurprise(BaseModel):
    risk_id: uuid.UUID
    project_id: uuid.UUID
    project_title: str
    statement: str
    tags: list[str]


class SurpriseStats(BaseModel):
    rate_per_project: float
    share: float | None
    n_surprises: int
    n_projects: int
    recent: list[RecentSurprise]


class MemberStat(BaseModel):
    user: UserRef
    n_graded: int
    brier: float | None
    bias: float | None


class WorkspaceCalibration(_SummaryFields):
    workspace_id: uuid.UUID
    sample: WorkspaceSample
    blind_spots: list[BlindSpot]
    false_alarms: list[BlindSpot]
    tags: list[TagCalibration]
    surprises: SurpriseStats
    members: list[MemberStat] | None
