from enum import StrEnum

from sqlalchemy.dialects.postgresql import ENUM


class WorkspaceRole(StrEnum):
    owner = "owner"
    admin = "admin"
    member = "member"


class ProjectStatus(StrEnum):
    planning = "planning"
    active = "active"
    closed = "closed"


class SessionPhase(StrEnum):
    collect = "collect"
    merge = "merge"
    vote = "vote"
    sealed = "sealed"


class RiskOrigin(StrEnum):
    participant = "participant"
    suggestion = "suggestion"
    surprise = "surprise"


class GradingOutcome(StrEnum):
    yes = "yes"
    no = "no"
    partial = "partial"


class LeadTeamSize(StrEnum):
    tiny = "1-10"
    small = "11-50"
    medium = "51-200"
    large = "200+"


class LeadStatus(StrEnum):
    new = "new"
    contacted = "contacted"
    accepted = "accepted"
    declined = "declined"


ROLE_ORDER: dict[WorkspaceRole, int] = {
    WorkspaceRole.member: 0,
    WorkspaceRole.admin: 1,
    WorkspaceRole.owner: 2,
}

OUTCOME_VALUE: dict[GradingOutcome, float] = {
    GradingOutcome.yes: 1.0,
    GradingOutcome.partial: 0.5,
    GradingOutcome.no: 0.0,
}


def pg_enum[E: StrEnum](enum_cls: type[E], name: str) -> ENUM:
    """Map a StrEnum onto an existing Postgres enum type (created by migrations)."""
    return ENUM(
        enum_cls,
        name=name,
        create_type=False,
        values_callable=lambda e: [m.value for m in e],
    )
