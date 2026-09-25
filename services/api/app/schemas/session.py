import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import SessionPhase
from app.schemas.common import UserRef


class SessionCounts(BaseModel):
    risks_total: int
    risks_canonical: int
    participants: int
    voters_complete: int


class SessionMe(BaseModel):
    is_facilitator: bool
    is_participant: bool
    risks_submitted: int
    votes_cast: int
    votes_required: int


class SessionOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    workspace_id: uuid.UUID
    phase: SessionPhase
    facilitator: UserRef
    created_by: UserRef
    phase_changed_at: datetime
    sealed_at: datetime | None
    fully_graded_at: datetime | None
    participants: list[UserRef]
    counts: SessionCounts
    me: SessionMe


class SessionCreate(BaseModel):
    participant_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)


class SessionPatch(BaseModel):
    facilitator_id: uuid.UUID


class SessionTransition(BaseModel):
    to: Literal["merge", "vote", "sealed"]


class SessionTransitionResult(BaseModel):
    session: SessionOut
    incomplete_voters: list[UserRef]


class ParticipantsAdd(BaseModel):
    user_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
