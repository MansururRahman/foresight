import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import Lead, LeadStatus, LeadTeamSize


def _lead(email: str = "ada@analytical.co") -> Lead:
    return Lead(
        name="Ada Lovelace",
        email=email,
        company="Analytical Ltd",
        role="Delivery lead",
        team_size=LeadTeamSize.small,
    )


async def test_lead_defaults_to_new_status(db_session):
    lead = _lead()
    db_session.add(lead)
    await db_session.flush()
    await db_session.refresh(lead)
    assert lead.status == LeadStatus.new
    assert lead.story is None and lead.source is None
    stored = await db_session.scalar(
        text("select team_size::text from leads where id = :id"), {"id": lead.id}
    )
    assert stored == "11-50"


async def test_lead_email_is_unique_case_insensitively(db_session):
    db_session.add(_lead("ada@analytical.co"))
    await db_session.flush()
    db_session.add(_lead("ADA@analytical.co"))
    with pytest.raises(IntegrityError):
        await db_session.flush()
