import uuid
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import verify_access_token
from app.db.session import get_session
from app.models import ROLE_ORDER, User, WorkspaceMember, WorkspaceRole
from app.services import users

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError(401, "missing_token", "Authorization header required")
    token = authorization.split(" ", 1)[1].strip()
    claims = await verify_access_token(token)
    return await users.upsert_from_claims(session, claims)


CurrentUser = Annotated[User, Depends(get_current_user)]


def not_found(what: str = "Resource") -> AppError:
    return AppError(404, "not_found", f"{what} not found")


async def require_membership(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user: User,
    min_role: WorkspaceRole = WorkspaceRole.member,
) -> WorkspaceMember:
    """404 for non-members (never leak existence), 403 for insufficient role."""
    member = await session.get(WorkspaceMember, (workspace_id, user.id))
    if member is None:
        raise not_found("Workspace")
    if ROLE_ORDER[member.role] < ROLE_ORDER[min_role]:
        raise AppError(403, "insufficient_role", f"This action requires the {min_role} role")
    return member


def is_admin(member: WorkspaceMember) -> bool:
    return ROLE_ORDER[member.role] >= ROLE_ORDER[WorkspaceRole.admin]
