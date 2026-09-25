"""Refresh-token families with rotation and reuse detection."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.keys import KeyPair
from app.core.security import hash_refresh, new_refresh_token, sign_access_token
from app.models.refresh_token import RefreshToken
from app.models.user import User


def _now() -> datetime:
    return datetime.now(UTC)


async def issue_pair(
    session: AsyncSession, user: User, kp: KeyPair, settings: Settings, user_agent: str | None
) -> tuple[str, str]:
    """Start a new refresh-token family and return (access_token, refresh_token)."""
    plain = new_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh(plain),
            family_id=uuid.uuid4(),
            expires_at=_now() + timedelta(days=settings.refresh_ttl_days),
            user_agent=user_agent,
        )
    )
    await session.commit()
    return sign_access_token(kp, user, settings), plain


async def _revoke_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


async def rotate(
    session: AsyncSession, presented: str, kp: KeyPair, settings: Settings, user_agent: str | None
) -> tuple[str, str, User]:
    """Exchange a live refresh token for a new pair. Replay of a rotated token kills the family."""
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh(presented))
    )
    if row is None:
        raise AppError(401, "invalid_refresh", "Refresh token not recognised")
    now = _now()
    if row.revoked_at is not None or row.replaced_by_id is not None:
        await _revoke_family(session, row.family_id)
        await session.commit()
        raise AppError(401, "refresh_reused", "Refresh token reuse detected; session revoked")
    if row.expires_at <= now:
        raise AppError(401, "refresh_expired", "Refresh token expired")
    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise AppError(401, "invalid_refresh", "User unavailable")

    plain = new_refresh_token()
    successor = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh(plain),
        family_id=row.family_id,
        expires_at=now + timedelta(days=settings.refresh_ttl_days),
        user_agent=user_agent,
    )
    session.add(successor)
    await session.flush()
    row.replaced_by_id = successor.id
    await session.commit()
    return sign_access_token(kp, user, settings), plain, user


async def revoke_family_by_token(session: AsyncSession, presented: str) -> None:
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh(presented))
    )
    if row is not None:
        await _revoke_family(session, row.family_id)
        await session.commit()
