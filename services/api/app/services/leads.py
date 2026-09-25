import csv
from typing import TextIO

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import RateLimiter
from app.models.enums import LeadStatus
from app.models.lead import Lead
from app.schemas.lead import LeadCreate

LEAD_RATE_LIMIT = 5
LEAD_RATE_WINDOW_SECONDS = 60

LEAD_LIMITER = RateLimiter(LEAD_RATE_LIMIT, LEAD_RATE_WINDOW_SECONDS)

_UPDATABLE = ("name", "company", "role", "team_size", "story")


async def submit(session: AsyncSession, data: LeadCreate) -> None:
    """Store or refresh an application. Honeypot hits are dropped silently.

    A repeat email updates the details but keeps `status` and `created_at`, so the
    response never reveals whether the address was already on the list. A repeat
    without a `source` keeps the stored one, so returning applicants keep their channel.
    """
    if data.website:
        return
    stmt = insert(Lead).values(**data.model_dump(exclude={"website"}))
    stmt = stmt.on_conflict_do_update(
        index_elements=[Lead.email],
        set_={
            **{col: stmt.excluded[col] for col in _UPDATABLE},
            "source": func.coalesce(stmt.excluded.source, Lead.source),
            "updated_at": func.now(),
        },
    )
    await session.execute(stmt)
    await session.commit()


EXPORT_COLUMNS = (
    "created_at",
    "name",
    "email",
    "company",
    "role",
    "team_size",
    "status",
    "source",
    "story",
)

# Cells starting with these are run as formulas by Excel/Sheets; the data comes from a public form.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _cell(value: str | None) -> str:
    if not value:
        return ""
    return f"'{value}" if value.startswith(_FORMULA_PREFIXES) else value


async def export_csv(session: AsyncSession, out: TextIO, status: LeadStatus | None = None) -> int:
    """Write leads as CSV (oldest first) and return how many rows were written."""
    stmt = select(Lead).order_by(Lead.created_at, Lead.id)
    if status is not None:
        stmt = stmt.where(Lead.status == status)
    rows = (await session.scalars(stmt)).all()
    writer = csv.writer(out)
    writer.writerow(EXPORT_COLUMNS)
    for lead in rows:
        writer.writerow(
            [
                lead.created_at.isoformat(),
                _cell(lead.name),
                _cell(lead.email),
                _cell(lead.company),
                _cell(lead.role),
                lead.team_size.value,
                lead.status.value,
                _cell(lead.source),
                _cell(lead.story),
            ]
        )
    return len(rows)
