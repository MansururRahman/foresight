# Landing Page & Design-Partner Applications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the anonymous `/` → `/login` redirect with a public landing page whose design-partner application form stores leads in the API database, exportable as CSV.

**Architecture:** A new `leads` table plus a public, rate-limited `POST /v1/leads` endpoint in `services/api` (router → service, as elsewhere), and a `python -m app.leads export` CLI. In `apps/web`, `/` becomes a server-rendered page made of small section components, with one client component (`LeadForm`) that posts through `apiFetch` with a new `auth: false` option. `proxy.ts` sends visitors with the session hint cookie from `/` to `/w`.

**Tech Stack:** FastAPI, async SQLAlchemy 2, Alembic, Pydantic v2 + `email-validator`, pytest; Next.js 16 App Router, Tailwind v4, shadcn/ui, TanStack Query, react-hook-form + zod, vitest + msw, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-25-landing-page-design.md`

## Global Constraints

- The endpoint path is `POST /v1/leads`. (The spec says `POST /leads`; every domain route in this API is under `/v1`, so the plan follows that convention.)
- Team sizes, exactly: `1-10`, `11-50`, `51-200`, `200+`. Statuses, exactly: `new`, `contacted`, `accepted`, `declined`.
- Field limits: name 1–120, company 1–160, role 1–120, story ≤2000, source ≤100 characters. Email is valid, trimmed and lowercased.
- Every accepted submission (new, repeat email, honeypot) returns `202 {"status": "received"}`.
- Rate limit: 5 requests per rolling 60 s per client IP → `429` with code `rate_limited`. The IP is never stored.
- No IP address or user agent is stored anywhere.
- The contact email is `hello@foresight.example` until the founder supplies a real one.
- Errors use the `{"error": {"code", "message", "details"}}` envelope.
- Migrations are hand-written: `0003_leads.py`, `down_revision = "0002"`.
- Next.js 16: read `apps/web/AGENTS.md` and the relevant files in `apps/web/node_modules/next/dist/docs/` before writing web code. Middleware is `proxy.ts`.
- Web dependencies install with `npm install --legacy-peer-deps`. Python dependencies go through `uv add` (from `services/api`).
- Quality gates: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy app` (strict), `uv run pytest`; `npm run lint`, `npm run typecheck`, `npm test`. Run `uv run ruff format .` before the checks; code in this plan may need rewrapping to 100 columns.
- `SITE_URL` (the absolute base URL for Open Graph images) defaults to `http://localhost:3000`. Setting it for production belongs to the deploy spec, not this plan.
- Deviation from spec: team size uses a native `<select>` styled with Tailwind rather than the base-ui `Select`. It works directly with `react-hook-form`'s `register`, is fully accessible, and is testable in jsdom; nothing in the repo tests the base-ui select.

## Review Focus

1. **Spreadsheet formula injection.** A lead named `=HYPERLINK("http://evil","x")` must export as inert text, because the founder will open the CSV in Excel. Pinned in Task 3.
2. **Email variants.** `"  Ada@Analytical.CO "` and `ada@analytical.co` must be one lead, not two. Pinned in Task 2.
3. **Story length boundary.** Exactly 2000 characters (including non-ASCII) is accepted and 2001 is rejected, both by the API and by the form. Pinned in Tasks 2 and 5.
4. **Double-click on submit.** Must send one request, not two. Pinned in Task 5.
5. **Network failure mid-submit.** Must show an error and keep everything the visitor typed. Pinned in Task 5.

---

### Task 1: `leads` table, enums and ORM model

**Files:**
- Modify: `services/api/app/models/enums.py`
- Create: `services/api/app/models/lead.py`
- Modify: `services/api/app/models/__init__.py`
- Create: `services/api/alembic/versions/0003_leads.py`
- Test: `services/api/tests/test_leads.py`

**Interfaces:**
- Produces: `app.models.LeadTeamSize` (StrEnum: `tiny="1-10"`, `small="11-50"`, `medium="51-200"`, `large="200+"`), `app.models.LeadStatus` (StrEnum: `new`, `contacted`, `accepted`, `declined`), `app.models.Lead` (ORM: `id, name, email, company, role, team_size, story, source, status, created_at, updated_at`).

Prerequisite: `docker compose up -d postgres` (tests use `localhost:5433`). Run all commands in this task from `services/api`.

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_leads.py`:

```python
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
```

- [ ] **Step 2: Run the test and check it fails**

Run: `uv run pytest tests/test_leads.py -q`
Expected: FAIL with `ImportError: cannot import name 'Lead' from 'app.models'`.

- [ ] **Step 3: Add the enums**

In `services/api/app/models/enums.py`, add after `GradingOutcome`:

```python
class LeadTeamSize(StrEnum):
    tiny = "1-10"
    small = "11-50"
    medium = "51-200"
    large = "200+"


class LeadStatus(StrEnum):
    new = "new"
    contacted = "contacted"
    accepted = "accepted"
    declined = "declined"
```

- [ ] **Step 4: Add the model**

Create `services/api/app/models/lead.py`:

```python
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import LeadStatus, LeadTeamSize, pg_enum


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A design-partner application from the public landing page."""

    __tablename__ = "leads"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(CITEXT(), unique=True, nullable=False)
    company: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    team_size: Mapped[LeadTeamSize] = mapped_column(
        pg_enum(LeadTeamSize, "lead_team_size"), nullable=False
    )
    story: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    status: Mapped[LeadStatus] = mapped_column(
        pg_enum(LeadStatus, "lead_status"),
        nullable=False,
        default=LeadStatus.new,
        server_default=LeadStatus.new.value,
    )
```

In `services/api/app/models/__init__.py`: add `LeadStatus, LeadTeamSize` to the `app.models.enums` import, add `from app.models.lead import Lead`, and add `"Lead"`, `"LeadStatus"`, `"LeadTeamSize"` to `__all__` in alphabetical order.

- [ ] **Step 5: Write the migration**

Create `services/api/alembic/versions/0003_leads.py`:

```python
"""leads: design-partner applications from the landing page

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)
NOW = sa.func.now()


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(name=name, create_type=False)


def upgrade() -> None:
    op.execute("CREATE TYPE lead_team_size AS ENUM ('1-10', '11-50', '51-200', '200+')")
    op.execute("CREATE TYPE lead_status AS ENUM ('new', 'contacted', 'accepted', 'declined')")
    op.create_table(
        "leads",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False, unique=True),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("team_size", _enum("lead_team_size"), nullable=False),
        sa.Column("story", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("status", _enum("lead_status"), nullable=False, server_default="new"),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 120", name="leads_name_len"),
        sa.CheckConstraint("length(company) BETWEEN 1 AND 160", name="leads_company_len"),
        sa.CheckConstraint("length(role) BETWEEN 1 AND 120", name="leads_role_len"),
        sa.CheckConstraint("story IS NULL OR length(story) <= 2000", name="leads_story_len"),
        sa.CheckConstraint("source IS NULL OR length(source) <= 100", name="leads_source_len"),
    )


def downgrade() -> None:
    op.drop_table("leads")
    op.execute("DROP TYPE IF EXISTS lead_status")
    op.execute("DROP TYPE IF EXISTS lead_team_size")
```

- [ ] **Step 6: Run the tests and check they pass**

Run: `uv run pytest tests/test_leads.py -q`
Expected: 2 passed. (The conftest downgrades to base and upgrades to head, so the new migration runs.)

- [ ] **Step 7: Run the full suite and the gates**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy app`
Expected: all pass. Run `uv run ruff format .` if the format check fails.

- [ ] **Step 8: Commit**

```bash
git add services/api/app/models services/api/alembic/versions/0003_leads.py services/api/tests/test_leads.py
git commit -m "feat(api): leads table for design-partner applications"
```

---

### Task 2: Public `POST /v1/leads` with honeypot, upsert and rate limit

**Files:**
- Modify: `services/api/pyproject.toml`, `services/api/uv.lock` (via `uv add`)
- Create: `services/api/app/core/ratelimit.py`
- Create: `services/api/app/schemas/lead.py`
- Create: `services/api/app/services/leads.py`
- Create: `services/api/app/routers/leads.py`
- Modify: `services/api/app/main.py`
- Test: `services/api/tests/test_ratelimit.py`, `services/api/tests/test_leads.py`

**Interfaces:**
- Consumes: `Lead`, `LeadTeamSize`, `LeadStatus` from Task 1.
- Produces:
  - `app.core.ratelimit.RateLimiter(max_requests: int, window_seconds: float, clock: Callable[[], float] = time.monotonic)` with `.hit(key: str) -> bool` (True = allowed) and `.reset() -> None`.
  - `app.schemas.lead.LeadCreate` and `LeadAccepted` (`status: Literal["received"]`).
  - `app.services.leads.submit(session: AsyncSession, data: LeadCreate) -> None`, `app.services.leads.LEAD_LIMITER: RateLimiter`.
  - `app.routers.leads.get_lead_limiter() -> RateLimiter` (FastAPI dependency).
  - HTTP: `POST /v1/leads` → 202 `{"status": "received"}` | 422 `validation_error` | 429 `rate_limited`.

Run all commands from `services/api`.

- [ ] **Step 1: Add the email validator dependency**

Run: `uv add "email-validator>=2.2"`
Expected: `pyproject.toml` dependencies and `uv.lock` updated.

- [ ] **Step 2: Write the failing rate limiter test**

Create `services/api/tests/test_ratelimit.py`:

```python
from app.core.ratelimit import RateLimiter


def test_allows_up_to_the_limit_per_key_then_blocks():
    now = [0.0]
    limiter = RateLimiter(2, 60, clock=lambda: now[0])
    assert limiter.hit("a") and limiter.hit("a")
    assert not limiter.hit("a")
    assert limiter.hit("b")  # keys are independent


def test_window_rolls_forward():
    now = [0.0]
    limiter = RateLimiter(2, 60, clock=lambda: now[0])
    limiter.hit("a")
    now[0] = 30.0
    limiter.hit("a")
    now[0] = 60.5  # the first hit has left the window
    assert limiter.hit("a")
    assert not limiter.hit("a")


def test_reset_clears_all_keys():
    limiter = RateLimiter(1, 60)
    limiter.hit("a")
    limiter.reset()
    assert limiter.hit("a")
```

- [ ] **Step 3: Run it and check it fails**

Run: `uv run pytest tests/test_ratelimit.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.ratelimit'`.

- [ ] **Step 4: Implement the rate limiter**

Create `services/api/app/core/ratelimit.py`:

```python
"""In-process sliding-window rate limiter. Per-instance only; fine for a single API replica."""

import time
from collections import deque
from collections.abc import Callable


class RateLimiter:
    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str) -> bool:
        """Record a request for `key`. Returns False when the key is over its limit."""
        now = self._clock()
        cutoff = now - self.window_seconds
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()
```

- [ ] **Step 5: Run the rate limiter tests**

Run: `uv run pytest tests/test_ratelimit.py -q`
Expected: 3 passed.

- [ ] **Step 6: Write the failing endpoint tests**

Append to `services/api/tests/test_leads.py` (add `from app.services.leads import LEAD_LIMITER` to the imports):

```python
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
```

- [ ] **Step 7: Run them and check they fail**

Run: `uv run pytest tests/test_leads.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.leads'`.

- [ ] **Step 8: Add the schemas**

Create `services/api/app/schemas/lead.py`:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import LeadTeamSize


class LeadCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    company: str = Field(min_length=1, max_length=160)
    role: str = Field(min_length=1, max_length=120)
    team_size: LeadTeamSize
    story: str | None = Field(default=None, max_length=2000)
    source: str | None = Field(default=None, max_length=100)
    # Honeypot: hidden in the form, so only bots fill it in.
    website: str = Field(default="", max_length=500)

    @field_validator("email", mode="before")
    @classmethod
    def _normalise_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("story", "source")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        return value or None


class LeadAccepted(BaseModel):
    status: Literal["received"] = "received"
```

- [ ] **Step 9: Add the service**

Create `services/api/app/services/leads.py`:

```python
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
```

- [ ] **Step 10: Add the router and register it**

Create `services/api/app/routers/leads.py`:

```python
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
```

In `services/api/app/main.py`: add `leads` to the `from app.routers import (...)` list (alphabetical, after `health`), and add `app.include_router(leads.router)` after `app.include_router(health.router)`.

- [ ] **Step 11: Run the tests and check they pass**

Run: `uv run pytest tests/test_leads.py tests/test_ratelimit.py -q`
Expected: all pass (2 + 7 + 7 parametrised + 3).

- [ ] **Step 12: Run the full suite and the gates**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy app`
Expected: all pass.

- [ ] **Step 13: Commit**

```bash
git add services/api/pyproject.toml services/api/uv.lock services/api/app services/api/tests
git commit -m "feat(api): public design-partner application endpoint"
```

---

### Task 3: CSV export CLI

**Files:**
- Modify: `services/api/app/services/leads.py`
- Create: `services/api/app/leads.py`
- Modify: `README.md`
- Test: `services/api/tests/test_leads.py`

**Interfaces:**
- Consumes: `Lead`, `LeadStatus` (Task 1); `app/services/leads.py` (Task 2).
- Produces: `app.services.leads.EXPORT_COLUMNS: tuple[str, ...]`, `app.services.leads.export_csv(session: AsyncSession, out: TextIO, status: LeadStatus | None = None) -> int`, `app.leads.main(argv: list[str] | None = None) -> None`. CLI: `python -m app.leads export [--status new|contacted|accepted|declined]`.

Run all commands from `services/api`.

- [ ] **Step 1: Write the failing tests**

Append to `services/api/tests/test_leads.py`. Add `import csv`, `import io` at the top, and `from app.leads import main as leads_cli` and `from app.services.leads import EXPORT_COLUMNS, export_csv` to the imports:

```python
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
```

- [ ] **Step 2: Run them and check they fail**

Run: `uv run pytest tests/test_leads.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.leads'`.

- [ ] **Step 3: Add `export_csv` to the service**

In `services/api/app/services/leads.py`, add `import csv` and `from typing import TextIO` at the top, extend the sqlalchemy import to `from sqlalchemy import func, select`, add `LeadStatus` via `from app.models.enums import LeadStatus`, then append:

```python
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
```

- [ ] **Step 4: Add the CLI**

Create `services/api/app/leads.py`:

```python
"""Lead tools. Usage: python -m app.leads export [--status new] > leads.csv"""

import argparse
import asyncio
import io
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.enums import LeadStatus
from app.services.leads import export_csv


async def _export(status: LeadStatus | None) -> None:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(newline="")  # the csv module writes its own line endings
    engine = create_async_engine(get_settings().database_url)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as db:
        n = await export_csv(db, sys.stdout, status)
    await engine.dispose()
    print(f"{n} leads exported", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.leads")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="write leads as CSV to stdout")
    export.add_argument("--status", choices=[s.value for s in LeadStatus])
    args = parser.parse_args(argv)
    asyncio.run(_export(LeadStatus(args.status) if args.status else None))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the tests and check they pass**

Run: `uv run pytest tests/test_leads.py -q`
Expected: all pass.

- [ ] **Step 6: Document the command**

In `README.md`, at the end of the `## What to try` section, add:

```markdown
### Design-partner applications

The landing page at `/` stores applications in the api database. Export them as CSV:

```bash
docker compose run --rm api python -m app.leads export > leads.csv
docker compose run --rm api python -m app.leads export --status new > new-leads.csv
```
```

- [ ] **Step 7: Run the full suite and the gates**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy app`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add services/api/app services/api/tests README.md
git commit -m "feat(api): CSV export for design-partner applications"
```

---

### Task 4: Unauthenticated `apiFetch` and the `useSubmitLead` mutation

**Files:**
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/lib/types.ts`
- Create: `apps/web/lib/queries/leads.ts`
- Test: `apps/web/__tests__/api.test.ts`

**Interfaces:**
- Consumes: HTTP `POST /v1/leads` (Task 2).
- Produces:
  - `ApiInit<T>.auth?: boolean` (default `true`).
  - In `lib/types.ts`: `TEAM_SIZES = ["1-10", "11-50", "51-200", "200+"] as const`, `type TeamSize`, `type LeadCreate = { name: string; email: string; company: string; role: string; team_size: TeamSize; story: string | null; source: string | null; website: string }`.
  - `useSubmitLead()` in `lib/queries/leads.ts`: a TanStack mutation taking `LeadCreate` and resolving `{ status: "received" }`.

Before starting: read `apps/web/AGENTS.md`. Run commands from `apps/web`.

- [ ] **Step 1: Write the failing tests**

Append inside the `describe("apiFetch", ...)` block in `apps/web/__tests__/api.test.ts`:

```ts
  it("sends no bearer token when auth is false", async () => {
    let seen: string | null = "unset";
    server.use(
      http.post(`${API_URL}/v1/leads`, ({ request }) => {
        seen = request.headers.get("authorization");
        return HttpResponse.json({ status: "received" }, { status: 202 });
      }),
    );
    setAccessToken("tok1");
    const result = await apiFetch<{ status: string }>("/v1/leads", { method: "POST", body: {}, auth: false });
    expect(result).toEqual({ status: "received" });
    expect(seen).toBeNull();
  });

  it("does not refresh or end the session on a 401 when auth is false", async () => {
    const onUnauthorized = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    server.use(
      http.post(`${API_URL}/v1/leads`, () =>
        HttpResponse.json({ error: { code: "nope", message: "no", details: {} } }, { status: 401 }),
      ),
    );
    // No refresh handler is registered: onUnhandledRequest "error" fails the test if one is attempted.
    const err = await apiFetch("/v1/leads", { method: "POST", body: {}, auth: false }).catch((e: unknown) => e);
    window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).not.toBeInstanceOf(UnauthorizedError);
    expect((err as ApiError).code).toBe("nope");
    expect(onUnauthorized).not.toHaveBeenCalled();
  });
```

- [ ] **Step 2: Run them and check they fail**

Run: `npx vitest run __tests__/api.test.ts`
Expected: FAIL. `typecheck` would reject `auth`; at runtime the first test sees `Bearer tok1`, and the second attempts a refresh (unhandled request error).

- [ ] **Step 3: Implement the `auth` option**

In `apps/web/lib/api.ts`:

1. Add to `ApiInit<T>`, after `signal?: AbortSignal;`:

```ts
  /** false for public endpoints: no bearer token, no refresh/sign-out on 401. */
  auth?: boolean;
```

2. In `apiFetch`, replace the destructuring and the send/refresh block:

```ts
  const { method = "GET", body, schema, signal, auth = true } = init;
```

```ts
  let res = await send(auth ? getAccessToken() : null);
  if (res.status === 401 && auth) {
    const token = await refresh();
    if (!token) sessionOver();
    res = await send(token);
    if (res.status === 401) sessionOver();
  }
```

3. Update the file's doc comment's first sentence to: `Typed fetch wrapper for the domain API. Attaches the bearer token (unless auth: false), and on a 401 performs one silent refresh and retries once.`

- [ ] **Step 4: Add the types and the mutation hook**

Append to `apps/web/lib/types.ts`:

```ts
export const TEAM_SIZES = ["1-10", "11-50", "51-200", "200+"] as const;
export type TeamSize = (typeof TEAM_SIZES)[number];

export type LeadCreate = {
  name: string;
  email: string;
  company: string;
  role: string;
  team_size: TeamSize;
  story: string | null;
  source: string | null;
  /** Honeypot; always "" from real visitors. */
  website: string;
};
```

Create `apps/web/lib/queries/leads.ts`:

```ts
"use client";

import { useMutation } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { LeadCreate } from "@/lib/types";

export function useSubmitLead() {
  return useMutation({
    mutationFn: (body: LeadCreate) =>
      apiFetch<{ status: "received" }>("/v1/leads", { method: "POST", body, auth: false }),
  });
}
```

- [ ] **Step 5: Run the tests and gates**

Run: `npx vitest run __tests__/api.test.ts && npm run typecheck && npm run lint`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add apps/web/lib apps/web/__tests__/api.test.ts
git commit -m "feat(web): unauthenticated apiFetch and lead submission hook"
```

---

### Task 5: `LeadForm` and the landing copy

**Files:**
- Create: `apps/web/content/landing.ts`
- Create: `apps/web/components/landing/LeadForm.tsx`
- Test: `apps/web/__tests__/LeadForm.test.tsx`

**Interfaces:**
- Consumes: `useSubmitLead`, `TEAM_SIZES`, `TeamSize`, `LeadCreate` (Task 4); `ApiError` from `@/lib/api`.
- Produces:
  - `landing` (the copy object) from `@/content/landing`, used by Task 6.
  - `LeadForm` (client component, no props) and `readSource(params: { get(name: string): string | null }): string | null` from `@/components/landing/LeadForm`.

Run commands from `apps/web`.

- [ ] **Step 1: Write the copy file**

Create `apps/web/content/landing.ts`:

```ts
// All landing-page copy. Edit wording here; layout lives in components/landing/.
export const landing = {
  meta: {
    title: "Foresight: pre-mortems that make your team better at predicting risk",
    description:
      "Anonymous pre-mortems for project teams, scored against what actually happened, so your team's foresight improves with every project.",
  },
  nav: { login: "Log in", cta: "Apply as design partner" },
  hero: {
    headline: "Your team saw it coming. Nobody wrote it down.",
    subhead:
      "Foresight runs anonymous pre-mortems for project teams, then scores who predicted what, so your team's foresight gets measurably better with every project.",
    cta: "Apply as design partner",
    note: "Free for design partners.",
  },
  problem: {
    heading: "Why the same surprises keep happening",
    items: [
      {
        title: "Risks go unspoken in meetings",
        body: "The junior who spotted the vendor problem stays quiet when the lead says it'll be fine.",
      },
      {
        title: "Risk registers are written once",
        body: "Nobody checks at the end which predictions came true, so nobody learns from them.",
      },
      {
        title: "Retros don't measure improvement",
        body: "You talk about what went wrong, but you can't tell whether your team is getting better at seeing it.",
      },
    ],
  },
  howItWorks: {
    heading: "How it works",
    steps: [
      { title: "Predict", body: "Everyone privately lists what could sink the project." },
      { title: "Merge & vote", body: "Duplicates are merged, then each person rates probability and impact on their own." },
      { title: "Seal", body: "The forecast is locked. Only team aggregates are shown, never individual votes." },
      { title: "Grade", body: "At close-out, mark what actually happened and see how well-calibrated everyone was." },
    ],
    screenshotAlt: "Foresight calibration dashboard showing a reliability diagram and Brier score",
  },
  benefits: {
    heading: "What you get",
    items: [
      { title: "Anonymous input", body: "People say what they actually think, not what the room expects." },
      { title: "Calibration scores", body: "Per person and per team, tracked across projects." },
      { title: "Blind-spot detection", body: "See which kinds of risk your team keeps missing." },
      { title: "Suggestions from history", body: "New projects start from the risks that bit similar projects before." },
    ],
  },
  offer: {
    heading: "Become a design partner",
    body: "We're working with 10 delivery teams to shape Foresight.",
    gives: ["Free access during the programme", "Direct input on the roadmap"],
    asks: ["Run one real project through Foresight", "Join two 30-minute feedback calls"],
  },
  form: {
    heading: "Apply",
    labels: {
      name: "Name",
      email: "Work email",
      company: "Company",
      role: "Role",
      teamSize: "Team size",
      teamSizePlaceholder: "Choose…",
      story: "What went wrong on your last project that someone probably saw coming?",
      storyHint: "Optional",
    },
    submit: "Apply",
    submitting: "Sending…",
    success: "Thanks, we'll reach out within 2 business days.",
    errors: {
      generic: "Something went wrong. Please try again.",
      rateLimited: "Too many attempts. Please wait a minute and try again.",
    },
  },
  footer: {
    contactEmail: "hello@foresight.example",
    privacy: "We only use this to contact you about the design partner programme.",
  },
} as const;
```

- [ ] **Step 2: Write the failing tests**

Create `apps/web/__tests__/LeadForm.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { LeadForm, readSource } from "@/components/landing/LeadForm";
import { API_URL } from "@/lib/env";

const nav = vi.hoisted(() => ({ params: new URLSearchParams() }));
vi.mock("next/navigation", () => ({ useSearchParams: () => nav.params }));

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  nav.params = new URLSearchParams();
});
afterAll(() => server.close());

function wrap() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <LeadForm />
    </QueryClientProvider>,
  );
}

async function fillValid(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Name"), "Ada Lovelace");
  await user.type(screen.getByLabelText("Work email"), "Ada@Analytical.co");
  await user.type(screen.getByLabelText("Company"), "Analytical Ltd");
  await user.type(screen.getByLabelText("Role"), "Delivery lead");
  await user.selectOptions(screen.getByLabelText("Team size"), "11-50");
}

describe("readSource", () => {
  it("prefers ref, falls back to utm_source, truncates to 100", () => {
    expect(readSource(new URLSearchParams("ref=linkedin&utm_source=x"))).toBe("linkedin");
    expect(readSource(new URLSearchParams("utm_source=newsletter"))).toBe("newsletter");
    expect(readSource(new URLSearchParams(""))).toBeNull();
    expect(readSource(new URLSearchParams(`ref=${"a".repeat(150)}`))).toHaveLength(100);
  });
});

describe("LeadForm", () => {
  it("shows validation messages and sends nothing when empty", async () => {
    const user = userEvent.setup();
    wrap();
    await user.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByText("Tell us your name")).toBeInTheDocument();
    expect(screen.getByText("Enter a valid work email")).toBeInTheDocument();
    expect(screen.getByText("Pick a team size")).toBeInTheDocument();
  });

  it("submits the expected body and shows the thank-you message", async () => {
    let body: unknown = null;
    server.use(
      http.post(`${API_URL}/v1/leads`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ status: "received" }, { status: 202 });
      }),
    );
    nav.params = new URLSearchParams("ref=linkedin");
    const user = userEvent.setup();
    wrap();
    await fillValid(user);
    await user.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Thanks, we'll reach out");
    expect(body).toEqual({
      name: "Ada Lovelace",
      email: "ada@analytical.co",
      company: "Analytical Ltd",
      role: "Delivery lead",
      team_size: "11-50",
      story: null,
      source: "linkedin",
      website: "",
    });
  });

  it("sends a single request on double click", async () => {
    let calls = 0;
    server.use(
      http.post(`${API_URL}/v1/leads`, async () => {
        calls += 1;
        await new Promise((r) => setTimeout(r, 50));
        return HttpResponse.json({ status: "received" }, { status: 202 });
      }),
    );
    const user = userEvent.setup();
    wrap();
    await fillValid(user);
    await user.dblClick(screen.getByRole("button", { name: "Apply" }));
    await screen.findByRole("status");
    expect(calls).toBe(1);
  });

  it("keeps what the visitor typed when the network fails", async () => {
    server.use(http.post(`${API_URL}/v1/leads`, () => HttpResponse.error()));
    const user = userEvent.setup();
    wrap();
    await fillValid(user);
    await user.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
    expect(screen.getByLabelText("Name")).toHaveValue("Ada Lovelace");
    expect(screen.getByRole("button", { name: "Apply" })).toBeEnabled();
  });

  it("shows the rate-limit message on 429", async () => {
    server.use(
      http.post(`${API_URL}/v1/leads`, () =>
        HttpResponse.json({ error: { code: "rate_limited", message: "slow", details: {} } }, { status: 429 }),
      ),
    );
    const user = userEvent.setup();
    wrap();
    await fillValid(user);
    await user.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Too many attempts");
  });

  it("accepts a 2000-character story and rejects 2001", async () => {
    const user = userEvent.setup();
    server.use(http.post(`${API_URL}/v1/leads`, () => HttpResponse.json({ status: "received" }, { status: 202 })));
    wrap();
    await fillValid(user);
    const story = screen.getByLabelText(/What went wrong/);
    await user.click(story);
    await user.paste("é".repeat(2001));
    await user.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByText("Keep it under 2000 characters")).toBeInTheDocument();
    await user.type(story, "{Backspace}");
    await user.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByRole("status")).toBeInTheDocument();
  });

  it("hides the honeypot from people and assistive tech", () => {
    wrap();
    expect(screen.queryByRole("textbox", { name: /website/i })).toBeNull();
  });
});
```

- [ ] **Step 3: Run them and check they fail**

Run: `npx vitest run __tests__/LeadForm.test.tsx`
Expected: FAIL with `Failed to resolve import "@/components/landing/LeadForm"`.

- [ ] **Step 4: Implement `LeadForm`**

Create `apps/web/components/landing/LeadForm.tsx`:

```tsx
"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useSearchParams } from "next/navigation";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { landing } from "@/content/landing";
import { ApiError } from "@/lib/api";
import { useSubmitLead } from "@/lib/queries/leads";
import { TEAM_SIZES, type TeamSize } from "@/lib/types";

const copy = landing.form;

const schema = z.object({
  name: z.string().trim().min(1, "Tell us your name").max(120, "Keep it under 120 characters"),
  email: z.string().trim().email("Enter a valid work email").max(254),
  company: z.string().trim().min(1, "Tell us where you work").max(160, "Keep it under 160 characters"),
  role: z.string().trim().min(1, "Tell us your role").max(120, "Keep it under 120 characters"),
  team_size: z.string().refine((v) => (TEAM_SIZES as readonly string[]).includes(v), "Pick a team size"),
  story: z.string().trim().max(2000, "Keep it under 2000 characters"),
  website: z.string(),
});
type Values = z.input<typeof schema>;

/** Which channel sent the visitor: `?ref=` wins over `?utm_source=`. */
export function readSource(params: { get(name: string): string | null }): string | null {
  const raw = (params.get("ref") ?? params.get("utm_source") ?? "").trim();
  return raw ? raw.slice(0, 100) : null;
}

function FieldError({ message }: { message?: string }) {
  return message ? <p className="text-sm text-destructive">{message}</p> : null;
}

export function LeadForm() {
  const params = useSearchParams();
  const submit = useSubmitLead();
  const inFlight = useRef(false);
  const [done, setDone] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", email: "", company: "", role: "", team_size: "", story: "", website: "" },
  });
  const errors = form.formState.errors;

  const onSubmit = form.handleSubmit(async (v) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setServerError(null);
    try {
      await submit.mutateAsync({
        name: v.name,
        email: v.email.toLowerCase(),
        company: v.company,
        role: v.role,
        team_size: v.team_size as TeamSize,
        story: v.story || null,
        source: readSource(params),
        website: v.website,
      });
      setDone(true);
    } catch (e) {
      setServerError(e instanceof ApiError && e.status === 429 ? copy.errors.rateLimited : copy.errors.generic);
    } finally {
      inFlight.current = false;
    }
  });

  if (done) {
    return (
      <p role="status" className="rounded-lg border bg-muted/40 p-6 text-center font-medium">
        {copy.success}
      </p>
    );
  }

  const pending = form.formState.isSubmitting || submit.isPending;

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="lead-name">{copy.labels.name}</Label>
          <Input id="lead-name" autoComplete="name" {...form.register("name")} />
          <FieldError message={errors.name?.message} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="lead-email">{copy.labels.email}</Label>
          <Input id="lead-email" type="email" autoComplete="email" {...form.register("email")} />
          <FieldError message={errors.email?.message} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="lead-company">{copy.labels.company}</Label>
          <Input id="lead-company" autoComplete="organization" {...form.register("company")} />
          <FieldError message={errors.company?.message} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="lead-role">{copy.labels.role}</Label>
          <Input id="lead-role" autoComplete="organization-title" {...form.register("role")} />
          <FieldError message={errors.role?.message} />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="lead-team-size">{copy.labels.teamSize}</Label>
        <select
          id="lead-team-size"
          className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30 sm:w-48"
          {...form.register("team_size")}
        >
          <option value="">{copy.labels.teamSizePlaceholder}</option>
          {TEAM_SIZES.map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
        <FieldError message={errors.team_size?.message} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="lead-story">
          {copy.labels.story} <span className="font-normal text-muted-foreground">({copy.labels.storyHint})</span>
        </Label>
        <Textarea id="lead-story" rows={4} {...form.register("story")} />
        <FieldError message={errors.story?.message} />
      </div>
      {/* Honeypot: off-screen and hidden from assistive tech; only bots fill it in. */}
      <div aria-hidden="true" className="absolute -left-[10000px] h-px w-px overflow-hidden">
        <label htmlFor="lead-website">Website</label>
        <input id="lead-website" tabIndex={-1} autoComplete="off" {...form.register("website")} />
      </div>
      {serverError && (
        <p role="alert" className="text-sm text-destructive">
          {serverError}
        </p>
      )}
      <Button type="submit" size="lg" className="w-full sm:w-auto" disabled={pending}>
        {pending ? copy.submitting : copy.submit}
      </Button>
    </form>
  );
}
```

Note: the story label begins with "What went wrong…" and ends with "(Optional)". The test finds it with the regex `/What went wrong/`.

- [ ] **Step 5: Run the tests and check they pass**

Run: `npx vitest run __tests__/LeadForm.test.tsx`
Expected: all pass. If the double-click test shows `calls === 2`, the `inFlight` ref guard is missing or reset too early. Fix the component, not the test.

- [ ] **Step 6: Run the gates**

Run: `npm test && npm run typecheck && npm run lint`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add apps/web/content apps/web/components/landing/LeadForm.tsx apps/web/__tests__/LeadForm.test.tsx
git commit -m "feat(web): design-partner application form"
```

---

### Task 6: Landing page sections, `/` route, metadata and proxy redirect

**Files:**
- Create: `apps/web/components/landing/LandingHeader.tsx`, `Hero.tsx`, `Problem.tsx`, `HowItWorks.tsx`, `Benefits.tsx`, `Offer.tsx`, `LandingFooter.tsx`
- Modify: `apps/web/app/page.tsx` (full rewrite)
- Modify: `apps/web/proxy.ts`
- Test: `apps/web/__tests__/proxy.test.ts`

**Interfaces:**
- Consumes: `landing` and `LeadForm` (Task 5).
- Produces: route `/` (static landing page for anonymous visitors); `proxy()` redirects `/` → `/w` when the `fs_session=1` cookie is present.

Before starting: read `node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/proxy.md` and `.../04-functions/use-search-params.md` (the Prerendering section: `LeadForm` must sit inside `<Suspense>`). Run commands from `apps/web`.

- [ ] **Step 1: Write the failing proxy tests**

Create `apps/web/__tests__/proxy.test.ts`:

```ts
// @vitest-environment node
import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { config, proxy } from "@/proxy";

const BASE = "http://localhost:3000";

function req(path: string, cookie?: string) {
  return new NextRequest(`${BASE}${path}`, cookie ? { headers: { cookie } } : undefined);
}

describe("proxy", () => {
  it("runs on the landing page", () => {
    expect(config.matcher).toContain("/");
  });

  it("sends signed-in visitors from / to /w", () => {
    const res = proxy(req("/?ref=linkedin", "fs_session=1"));
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toBe(`${BASE}/w`);
  });

  it("lets anonymous visitors see the landing page", () => {
    const res = proxy(req("/?ref=linkedin"));
    expect(res.headers.get("location")).toBeNull();
  });

  it("still sends anonymous visitors from /w to /login", () => {
    const res = proxy(req("/w"));
    expect(res.headers.get("location")).toBe(`${BASE}/login?next=%2Fw`);
  });
});
```

- [ ] **Step 2: Run them and check they fail**

Run: `npx vitest run __tests__/proxy.test.ts`
Expected: FAIL on "runs on the landing page" and "sends signed-in visitors from / to /w".

- [ ] **Step 3: Update the proxy**

In `apps/web/proxy.ts`, add this block at the top of `proxy()`, right after the `hasHint` line:

```ts
  if (pathname === "/" && hasHint) {
    const url = request.nextUrl.clone();
    url.pathname = "/w";
    url.search = "";
    return NextResponse.redirect(url);
  }
```

and change the matcher to:

```ts
  matcher: ["/", "/w/:path*", "/login", "/register"],
```

- [ ] **Step 4: Run the proxy tests**

Run: `npx vitest run __tests__/proxy.test.ts`
Expected: 4 passed.

- [ ] **Step 5: Write the section components**

All are server components (no `"use client"`). Links styled as buttons use `buttonVariants`, because this `Button` is a base-ui element and has no `asChild`.

`apps/web/components/landing/LandingHeader.tsx`:

```tsx
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { landing } from "@/content/landing";

export function LandingHeader() {
  return (
    <header className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
      <span className="text-lg font-semibold tracking-tight">Foresight</span>
      <nav className="flex items-center gap-2">
        <Link href="/login" className={buttonVariants({ variant: "ghost" })}>
          {landing.nav.login}
        </Link>
        <a href="#apply" className={buttonVariants()}>
          {landing.nav.cta}
        </a>
      </nav>
    </header>
  );
}
```

`apps/web/components/landing/Hero.tsx`:

```tsx
import { buttonVariants } from "@/components/ui/button";
import { landing } from "@/content/landing";

export function Hero() {
  const { headline, subhead, cta, note } = landing.hero;
  return (
    <section className="mx-auto max-w-3xl px-4 py-16 text-center sm:py-24">
      <h1 className="text-4xl font-bold tracking-tight text-balance sm:text-5xl">{headline}</h1>
      <p className="mt-6 text-lg text-pretty text-muted-foreground">{subhead}</p>
      <div className="mt-8 flex flex-col items-center gap-2">
        <a href="#apply" className={buttonVariants({ size: "lg" })}>
          {cta}
        </a>
        <p className="text-sm text-muted-foreground">{note}</p>
      </div>
    </section>
  );
}
```

`apps/web/components/landing/Problem.tsx`:

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { landing } from "@/content/landing";

export function Problem() {
  return (
    <section className="mx-auto max-w-5xl px-4 py-12">
      <h2 className="text-center text-2xl font-semibold tracking-tight">{landing.problem.heading}</h2>
      <div className="mt-8 grid gap-4 md:grid-cols-3">
        {landing.problem.items.map((item) => (
          <Card key={item.title}>
            <CardHeader>
              <CardTitle>{item.title}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">{item.body}</CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
```

`apps/web/components/landing/HowItWorks.tsx`:

```tsx
import Image from "next/image";

import { landing } from "@/content/landing";

export function HowItWorks() {
  const { heading, steps, screenshotAlt } = landing.howItWorks;
  return (
    <section className="mx-auto max-w-5xl px-4 py-12">
      <h2 className="text-center text-2xl font-semibold tracking-tight">{heading}</h2>
      <ol className="mt-8 grid gap-6 md:grid-cols-4">
        {steps.map((step, i) => (
          <li key={step.title} className="space-y-2">
            <span className="flex size-8 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
              {i + 1}
            </span>
            <h3 className="font-medium">{step.title}</h3>
            <p className="text-sm text-muted-foreground">{step.body}</p>
          </li>
        ))}
      </ol>
      <Image
        src="/landing/calibration.png"
        alt={screenshotAlt}
        width={1280}
        height={800}
        className="mt-10 w-full rounded-xl border shadow-sm"
      />
    </section>
  );
}
```

`apps/web/components/landing/Benefits.tsx`:

```tsx
import { landing } from "@/content/landing";

export function Benefits() {
  return (
    <section className="mx-auto max-w-5xl px-4 py-12">
      <h2 className="text-center text-2xl font-semibold tracking-tight">{landing.benefits.heading}</h2>
      <dl className="mt-8 grid gap-6 sm:grid-cols-2">
        {landing.benefits.items.map((item) => (
          <div key={item.title} className="rounded-lg border p-5">
            <dt className="font-medium">{item.title}</dt>
            <dd className="mt-1 text-sm text-muted-foreground">{item.body}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
```

`apps/web/components/landing/Offer.tsx` (wraps the form section, so `#apply` lands on the offer and the form together):

```tsx
import { landing } from "@/content/landing";

export function Offer({ children }: { children: React.ReactNode }) {
  const { heading, body, gives, asks } = landing.offer;
  return (
    <section id="apply" className="mx-auto max-w-3xl scroll-mt-8 px-4 py-12">
      <h2 className="text-2xl font-semibold tracking-tight">{heading}</h2>
      <p className="mt-2 text-muted-foreground">{body}</p>
      <div className="mt-6 grid gap-6 sm:grid-cols-2">
        <div>
          <h3 className="text-sm font-medium">You get</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {gives.map((g) => (
              <li key={g}>{g}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="text-sm font-medium">We ask</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {asks.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
      </div>
      <div className="relative mt-8 rounded-xl border p-6">
        <h3 className="mb-4 text-lg font-semibold">{landing.form.heading}</h3>
        {children}
      </div>
    </section>
  );
}
```

`apps/web/components/landing/LandingFooter.tsx`:

```tsx
import { landing } from "@/content/landing";

export function LandingFooter() {
  const { contactEmail, privacy } = landing.footer;
  return (
    <footer className="mx-auto max-w-5xl border-t px-4 py-8 text-sm text-muted-foreground">
      <div className="flex flex-col justify-between gap-2 sm:flex-row">
        <span>© {new Date().getFullYear()} Foresight</span>
        <a href={`mailto:${contactEmail}`} className="underline underline-offset-4">
          {contactEmail}
        </a>
      </div>
      <p className="mt-2">{privacy}</p>
    </footer>
  );
}
```

- [ ] **Step 6: Rewrite the page**

Replace `apps/web/app/page.tsx` entirely:

```tsx
import type { Metadata } from "next";
import { Suspense } from "react";

import { Benefits } from "@/components/landing/Benefits";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { LandingFooter } from "@/components/landing/LandingFooter";
import { LandingHeader } from "@/components/landing/LandingHeader";
import { LeadForm } from "@/components/landing/LeadForm";
import { Offer } from "@/components/landing/Offer";
import { Problem } from "@/components/landing/Problem";
import { landing } from "@/content/landing";

// Signed-in visitors never reach this page: proxy.ts redirects `/` to `/w` when the session hint is set.
export const metadata: Metadata = {
  metadataBase: new URL(process.env.SITE_URL ?? "http://localhost:3000"),
  title: { absolute: landing.meta.title },
  description: landing.meta.description,
  openGraph: {
    title: landing.meta.title,
    description: landing.meta.description,
    images: [{ url: "/landing/calibration.png", width: 1280, height: 800 }],
  },
};

export default function LandingPage() {
  return (
    <>
      <LandingHeader />
      <main>
        <Hero />
        <Problem />
        <HowItWorks />
        <Benefits />
        <Offer>
          {/* LeadForm reads ?ref= via useSearchParams, which needs a Suspense boundary on a prerendered page. */}
          <Suspense fallback={<div className="h-96" aria-busy="true" />}>
            <LeadForm />
          </Suspense>
        </Offer>
      </main>
      <LandingFooter />
    </>
  );
}
```

- [ ] **Step 7: Add a placeholder screenshot so the build works before Task 7**

Run (from `apps/web`): `mkdir -p public/landing && node -e "require('fs').writeFileSync('public/landing/calibration.png', Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=','base64'))"`
Expected: a 1×1 `public/landing/calibration.png` exists. Task 7 replaces it with the real screenshot.

- [ ] **Step 8: Verify the build and the gates**

Run: `npm test && npm run typecheck && npm run lint && npm run build`
Expected: all pass. The build output lists `/` as static (`○`). If the build fails with "useSearchParams() should be wrapped in a suspense boundary", the `<Suspense>` in Step 6 is missing.

- [ ] **Step 9: Check it in the browser**

Run `npm run dev` (with the API up: `docker compose up -d`). Open `http://localhost:3000/?ref=manual` in a private window:
- all eight sections render, and both CTAs scroll to the form
- submitting a valid application shows the thank-you message
- `docker compose run --rm api python -m app.leads export` lists it with source `manual`
- after logging in, opening `/` lands on `/w`

- [ ] **Step 10: Commit**

```bash
git add apps/web/app/page.tsx apps/web/proxy.ts apps/web/components/landing apps/web/public/landing apps/web/__tests__/proxy.test.ts
git commit -m "feat(web): public landing page at /"
```

---

### Task 7: Real screenshot, e2e coverage and final verification

**Files:**
- Create: `apps/web/scripts/capture-landing-screenshot.mjs`
- Modify: `apps/web/public/landing/calibration.png` (real screenshot)
- Create: `apps/web/e2e/landing.spec.ts`

**Interfaces:**
- Consumes: the running, seeded stack (`docker compose up -d --build`, then `docker compose run --rm api python -m app.seed`), the landing page (Task 6), and `loginViaUi` from `e2e/helpers.ts`.
- Produces: the committed `public/landing/calibration.png` (1280×800) and `e2e/landing.spec.ts`.

Run commands from `apps/web`.

- [ ] **Step 1: Rebuild and seed the stack**

Run (repo root): `docker compose up -d --build && docker compose run --rm api python -m app.seed`
Expected: all services healthy; the seed prints "Demo workspace ready".

- [ ] **Step 2: Write the e2e spec**

Create `apps/web/e2e/landing.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

import { loginViaUi } from "./helpers";

test("anonymous visitors see the landing page and can apply", async ({ page }) => {
  await page.goto("/?ref=e2e");
  await expect(page.getByRole("heading", { level: 1, name: /Your team saw it coming/ })).toBeVisible();

  await page.getByRole("link", { name: "Apply as design partner" }).first().click();
  await page.getByLabel("Name", { exact: true }).fill("E2E Lead");
  await page.getByLabel("Work email").fill(`lead-${Date.now()}@foresight-e2e.dev`);
  await page.getByLabel("Company").fill("E2E Consulting");
  await page.getByLabel("Role", { exact: true }).fill("Delivery lead");
  await page.getByLabel("Team size").selectOption("11-50");
  await page.getByRole("button", { name: "Apply", exact: true }).click();

  await expect(page.getByRole("status")).toContainText("Thanks, we'll reach out");
});

test("signed-in users opening / land in the app", async ({ page }) => {
  await loginViaUi(page, "ada@demo.local");
  await page.goto("/");
  await expect(page).toHaveURL(/\/w$/);
});
```

(The email domain is deliberately not `.local`: `email-validator` rejects special-use domains.)

- [ ] **Step 3: Run the e2e suite**

Run: `npm run e2e`
Expected: all specs pass, including the existing `auth`, `dashboard` and `session-flow` specs.

- [ ] **Step 4: Write the screenshot script**

Create `apps/web/scripts/capture-landing-screenshot.mjs`:

```js
// Captures the seeded demo's calibration dashboard for the landing page.
// Needs the running, seeded stack. Usage: node scripts/capture-landing-screenshot.mjs
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
// fileURLToPath handles Windows drive letters and the spaces in this repo's OneDrive path.
const OUT = fileURLToPath(new URL("../public/landing/calibration.png", import.meta.url));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, colorScheme: "light" });
await page.goto(`${BASE}/login`);
await page.getByLabel("Email").fill("ada@demo.local");
await page.getByLabel("Password").fill("demo1234");
await page.getByRole("button", { name: "Sign in" }).click();
await page.waitForURL(/\/w/);
await page.getByRole("link", { name: /Demo Team/ }).click();
await page.getByRole("link", { name: "Dashboard" }).click();
await page.getByRole("heading", { name: "Team calibration" }).waitFor();
await page.getByTestId("bin-dot").first().waitFor();
await page.waitForTimeout(500); // let chart animations settle
await page.screenshot({ path: OUT });
await browser.close();
console.log(`saved ${OUT}`);
```

- [ ] **Step 5: Capture the screenshot and check it**

Run: `node scripts/capture-landing-screenshot.mjs`
Expected: prints `saved …/public/landing/calibration.png`. Open the image: it should show the Team calibration dashboard with the reliability diagram and no error states. Reload `http://localhost:3000/` in a private window and confirm the screenshot appears in "How it works".

- [ ] **Step 6: Run every quality gate**

Run from `services/api`: `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy app`
Run from `apps/web`: `npm test && npm run typecheck && npm run lint && npm run build`
Expected: all pass. Record the pass counts in the final report.

- [ ] **Step 7: Commit**

```bash
git add apps/web/scripts/capture-landing-screenshot.mjs apps/web/public/landing/calibration.png apps/web/e2e/landing.spec.ts
git commit -m "test(web): landing page e2e and real dashboard screenshot"
```
