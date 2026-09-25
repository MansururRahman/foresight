from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.core.errors import AppError
from app.core.ratelimit import RateLimiter
from app.deps import SessionDep
from app.schemas.lead import LeadAccepted, LeadCreate
from app.services import leads

router = APIRouter(prefix="/v1/leads", tags=["leads"])


def get_lead_limiter() -> RateLimiter:
    return leads.LEAD_LIMITER


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=LeadAccepted)
async def submit_lead(
    body: LeadCreate,
    request: Request,
    session: SessionDep,
    limiter: Annotated[RateLimiter, Depends(get_lead_limiter)],
) -> LeadAccepted:
    """Public: design-partner application from the landing page. No auth."""
    client_ip = request.client.host if request.client else "unknown"
    if not limiter.hit(client_ip):
        raise AppError(429, "rate_limited", "Too many submissions. Please try again in a minute.")
    await leads.submit(session, body)
    return LeadAccepted()
