import uuid
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.keys import KeyPair, load_keypair
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.user import User


@lru_cache
def get_keypair() -> KeyPair:
    return load_keypair(get_settings())


SettingsDep = Annotated[Settings, Depends(get_settings)]
KeyPairDep = Annotated[KeyPair, Depends(get_keypair)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    settings: SettingsDep,
    kp: KeyPairDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError(401, "missing_token", "Authorization header required")
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = decode_access_token(token, kp, settings)
    except jwt.PyJWTError as exc:
        raise AppError(401, "invalid_token", "Access token is invalid or expired") from exc
    user = await session.get(User, uuid.UUID(str(claims["sub"])))
    if user is None or not user.is_active:
        raise AppError(401, "invalid_token", "User unavailable")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
