"""Hidden voting and seal-time aggregation. Implemented in Task 9; the seal is stubbed here."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import PremortemSession
from app.schemas.common import UserRef


async def seal(db: AsyncSession, sess: PremortemSession) -> list[UserRef]:
    raise AppError(501, "not_implemented", "Sealing is not available yet")
