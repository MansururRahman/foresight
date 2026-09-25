from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import RateLimiter
from app.models.lead import Lead
from app.schemas.lead import LeadCreate

LEAD_RATE_LIMIT = 5
LEAD_RATE_WINDOW_SECONDS = 60

LEAD_LIMITER = RateLimiter(LEAD_RATE_LIMIT, LEAD_RATE_WINDOW_SECONDS)

_UPDATABLE = ("name", "company", "role", "team_size", "story", "source")


async def submit(session: AsyncSession, data: LeadCreate) -> None:
    """Store or refresh an application. Honeypot hits are dropped silently.

    A repeat email updates the details but keeps `status` and `created_at`, so the
    response never reveals whether the address was already on the list.
    """
    if data.website:
        return
    stmt = insert(Lead).values(**data.model_dump(exclude={"website"}))
    stmt = stmt.on_conflict_do_update(
        index_elements=[Lead.email],
        set_={**{col: stmt.excluded[col] for col in _UPDATABLE}, "updated_at": func.now()},
    )
    await session.execute(stmt)
    await session.commit()
