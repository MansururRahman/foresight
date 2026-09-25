from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import verify_access_token
from app.db.session import get_session
from app.models.user import User
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
