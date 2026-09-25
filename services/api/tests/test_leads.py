import csv
import io

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.leads import main as leads_cli
from app.models import Lead, LeadStatus, LeadTeamSize
from app.services.leads import EXPORT_COLUMNS, LEAD_LIMITER, export_csv

PAYLOAD = {
    "name": "Ada Lovelace",
    "email": "ada@analytical.co",
    "company": "Analytical Ltd",
    "role": "Delivery lead",
    "team_size": "11-50",
    "story": "Vendor API was late; two people knew in week one.",
    "source": "linkedin",
    "website": "",
}


@pytest.fixture(autouse=True)
def _reset_limiter():
    LEAD_LIMITER.reset()
    yield
    LEAD_LIMITER.reset()


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


async def _row(db_session, email: str):
    result = await db_session.execute(
        text(
            "select name, email::text, company, role, team_size::text, story, source, "
            "status::text, created_at from leads where email = :e"
        ),
        {"e": email},
    )
    return result.mappings().one_or_none()


async def _count(db_session) -> int:
    return await db_session.scalar(text("select count(*) from leads"))


async def test_submit_stores_a_new_lead_without_auth(client, db_session):
    res = await client.post("/v1/leads", json=PAYLOAD)
    assert res.status_code == 202
    assert res.json() == {"status": "received"}
    row = await _row(db_session, "ada@analytical.co")
    assert row is not None
    assert row["team_size"] == "11-50"
    assert row["status"] == "new"
    assert row["source"] == "linkedin"


async def test_email_variants_are_one_lead(client, db_session):
    first = await client.post("/v1/leads", json={**PAYLOAD, "email": "  Ada@Analytical.CO "})
    second = await client.post("/v1/leads", json=PAYLOAD)
    assert first.status_code == second.status_code == 202
    assert await _count(db_session) == 1
    row = await _row(db_session, "ada@analytical.co")
    assert row["email"] == "ada@analytical.co"


async def test_repeat_email_updates_fields_but_keeps_status(client, db_session):
    await client.post("/v1/leads", json=PAYLOAD)
    await db_session.execute(text("update leads set status = 'contacted'"))
    before = await _row(db_session, "ada@analytical.co")

    res = await client.post(
        "/v1/leads", json={**PAYLOAD, "company": "Difference Engines AS", "story": ""}
    )
    assert res.status_code == 202
    after = await _row(db_session, "ada@analytical.co")
    assert await _count(db_session) == 1
    assert after["company"] == "Difference Engines AS"
    assert after["story"] is None  # empty strings become null
    assert after["status"] == "contacted"
    assert after["created_at"] == before["created_at"]


async def test_honeypot_is_accepted_but_not_stored(client, db_session):
    res = await client.post("/v1/leads", json={**PAYLOAD, "website": "http://spam.example"})
    assert res.status_code == 202
    assert res.json() == {"status": "received"}
    assert await _count(db_session) == 0


async def test_strings_are_trimmed(client, db_session):
    await client.post("/v1/leads", json={**PAYLOAD, "name": "  Ada  ", "source": "   "})
    row = await _row(db_session, "ada@analytical.co")
    assert row["name"] == "Ada"
    assert row["source"] is None


@pytest.mark.parametrize(
    "override",
    [
        {"email": "not-an-email"},
        {"name": "   "},
        {"company": ""},
        {"role": "x" * 121},
        {"team_size": "5-8"},
        {"story": "é" * 2001},
        {"source": "s" * 101},
    ],
)
async def test_invalid_input_returns_422_envelope(client, db_session, override):
    res = await client.post("/v1/leads", json={**PAYLOAD, **override})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"
    assert await _count(db_session) == 0


async def test_story_of_exactly_2000_characters_is_accepted(client, db_session):
    res = await client.post("/v1/leads", json={**PAYLOAD, "story": "é" * 2000})
    assert res.status_code == 202
    row = await _row(db_session, "ada@analytical.co")
    assert len(row["story"]) == 2000


async def test_sixth_request_in_a_minute_is_rate_limited(client, db_session):
    for i in range(5):
        res = await client.post("/v1/leads", json={**PAYLOAD, "email": f"lead{i}@analytical.co"})
        assert res.status_code == 202
    res = await client.post("/v1/leads", json={**PAYLOAD, "email": "lead5@analytical.co"})
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "rate_limited"
    assert await _count(db_session) == 5


async def test_export_writes_header_and_rows_oldest_first(client, db_session):
    await client.post("/v1/leads", json={**PAYLOAD, "email": "first@analytical.co"})
    await client.post("/v1/leads", json={**PAYLOAD, "email": "second@analytical.co", "story": ""})
    out = io.StringIO()
    n = await export_csv(db_session, out)
    rows = list(csv.reader(io.StringIO(out.getvalue())))
    assert n == 2
    assert tuple(rows[0]) == EXPORT_COLUMNS
    assert [r[2] for r in rows[1:]] == ["first@analytical.co", "second@analytical.co"]
    assert rows[1][5] == "11-50" and rows[1][6] == "new"
    assert rows[2][8] == ""  # null story exports as an empty cell


async def test_export_filters_by_status(client, db_session):
    await client.post("/v1/leads", json={**PAYLOAD, "email": "a@analytical.co"})
    await client.post("/v1/leads", json={**PAYLOAD, "email": "b@analytical.co"})
    await db_session.execute(
        text("update leads set status = 'accepted' where email = 'b@analytical.co'")
    )
    out = io.StringIO()
    n = await export_csv(db_session, out, LeadStatus.accepted)
    rows = list(csv.reader(io.StringIO(out.getvalue())))
    assert n == 1
    assert rows[1][2] == "b@analytical.co"


async def test_export_neutralises_spreadsheet_formulas(client, db_session):
    await client.post(
        "/v1/leads",
        json={
            **PAYLOAD,
            "name": '=HYPERLINK("http://evil.example","x")',
            "company": "+cmd",
            "role": "-2+3",
            "story": "@SUM(A1)",
        },
    )
    out = io.StringIO()
    await export_csv(db_session, out)
    row = list(csv.reader(io.StringIO(out.getvalue())))[1]
    assert row[1] == '\'=HYPERLINK("http://evil.example","x")'
    assert row[3] == "'+cmd"
    assert row[4] == "'-2+3"
    assert row[8] == "'@SUM(A1)"


def test_cli_rejects_unknown_status():
    with pytest.raises(SystemExit):
        leads_cli(["export", "--status", "bogus"])


async def test_repeat_without_source_keeps_the_first_source(client, db_session):
    await client.post("/v1/leads", json={**PAYLOAD, "source": "linkedin"})
    await client.post("/v1/leads", json={**PAYLOAD, "source": None})
    row = await _row(db_session, "ada@analytical.co")
    assert row["source"] == "linkedin"
