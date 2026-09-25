import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.risk import RiskOut
from app.schemas.session import SessionOut


class VoteIn(BaseModel):
    risk_id: uuid.UUID
    probability: int = Field(ge=0, le=100)
    impact: int = Field(ge=1, le=5)


class VotesPut(BaseModel):
    votes: list[VoteIn] = Field(min_length=1, max_length=500)


class MyVoteItem(BaseModel):
    risk_id: uuid.UUID
    probability: int
    impact: int
    updated_at: datetime


class MyVotes(BaseModel):
    items: list[MyVoteItem]
    required: int


class ResultRisk(RiskOut):
    histogram: list[int] | None


class Participation(BaseModel):
    participants: int
    voters_complete: int
    voters_partial: int
    voters_none: int


class ResultsOut(BaseModel):
    session: SessionOut
    risks: list[ResultRisk]
    participation: Participation
