import uuid

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Claims
from app.models.user import User


async def upsert_from_claims(session: AsyncSession, claims: Claims) -> User:
    """Insert or refresh the mirrored user row for the authenticated caller."""
    user_id = uuid.UUID(claims["sub"])
    stmt = (
        insert(User)
        .values(id=user_id, email=claims["email"], name=claims["name"])
        .on_conflict_do_update(
            index_elements=[User.id],
            set_={"email": claims["email"], "name": claims["name"], "last_seen_at": func.now()},
        )
        .returning(User)
    )
    result = await session.execute(stmt)
    user = result.scalar_one()
    await session.commit()
    return user
