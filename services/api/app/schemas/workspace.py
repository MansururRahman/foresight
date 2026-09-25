import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import WorkspaceRole
from app.schemas.common import UserRef


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, min_length=1, max_length=50)


class WorkspacePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)


class WorkspaceOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    my_role: WorkspaceRole
    created_at: datetime


class WorkspaceList(BaseModel):
    items: list[WorkspaceOut]


class MemberOut(BaseModel):
    user: UserRef
    role: WorkspaceRole
    joined_at: datetime


class MemberList(BaseModel):
    items: list[MemberOut]


class MemberAdd(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    role: WorkspaceRole = WorkspaceRole.member


class MemberRoleSet(BaseModel):
    role: WorkspaceRole


class TagStat(BaseModel):
    tag: str
    project_count: int
    risk_count: int


class TagList(BaseModel):
    items: list[TagStat]
