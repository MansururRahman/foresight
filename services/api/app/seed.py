"""Demo data for a first run: three personas, four graded projects, one live session.

Run inside the api container:  python -m app.seed
The auth service must be reachable (AUTH_URL, default http://auth:8001) because users are
registered through its HTTP API - the domain API never writes the auth database.

Personas (deterministic with SEED):
  Ada    - well calibrated: says roughly what the true rate is.
  Grace  - overconfident: pushes every estimate to the extremes.
  Linus  - underconfident: hedges everything toward 50%.
"""

from __future__ import annotations

import asyncio
import os
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TypedDict

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import (
    Grading,
    GradingOutcome,
    PremortemSession,
    Project,
    ProjectStatus,
    Risk,
    RiskOrigin,
    SessionParticipant,
    SessionPhase,
    User,
    Vote,
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
)
from app.services.votes import aggregate

PASSWORD = "demo1234"
WORKSPACE_SLUG = "demo"
USERS: list[tuple[str, str]] = [
    ("ada@demo.local", "Ada Lovelace"),
    ("grace@demo.local", "Grace Hopper"),
    ("linus@demo.local", "Linus Torvalds"),
]

STATEMENTS: dict[str, list[str]] = {
    "scope": [
        "Scope creep from marketing adds features mid-sprint",
        "Requirements change after the design is signed off",
        "Stakeholders disagree on what done means",
        "A must-have integration is discovered late",
    ],
    "tech": [
        "Data migration needs a rollback",
        "Load test fails at expected peak traffic",
        "Legacy module has no tests and breaks silently",
        "Staging environment differs from production",
    ],
    "people": [
        "Key engineer on leave during the critical path",
        "Onboarding a new team member slows the sprint",
        "Nobody owns support after launch",
        "Reviewer bandwidth becomes the bottleneck",
    ],
    "external": [
        "Legal review slips by weeks",
        "Security audit requests late changes",
        "Compliance rules change during the project",
        "A partner API deprecates an endpoint we depend on",
    ],
    "timeline": [
        "Timeline too tight for QA",
        "Holiday period removes two weeks of capacity",
        "Dependency team delivers late",
        "Estimates omit deployment and hardening work",
    ],
    "vendor": [
        "Vendor API not ready by integration start",
        "Vendor pricing changes mid-project",
        "Vendor sandbox differs from production behaviour",
        "Vendor support is slow to respond to blockers",
    ],
}

SURPRISES: list[tuple[str, list[str]]] = [
    ("Legal blocked the data-residency clause for three weeks", ["legal", "external"]),
    ("The CDN provider had a regional outage on launch day", ["external", "tech"]),
    ("Finance froze the budget for a quarter-end review", ["external", "timeline"]),
    ("A duplicate project was discovered in another department", ["scope", "people"]),
    ("The app store rejected the build over a privacy label", ["external", "vendor"]),
    ("A core library shipped a breaking change in a patch release", ["tech", "vendor"]),
]


class ProjectSpec(TypedDict):
    title: str
    description: str
    tags: list[str]
    closed_days_ago: int
    duration_days: int
    surprises: int


PROJECTS: list[ProjectSpec] = [
    {
        "title": "Checkout Rewrite",
        "description": "Replace the legacy checkout with a new payments flow and a new vendor.",
        "tags": ["tech", "vendor", "timeline"],
        "closed_days_ago": 150,
        "duration_days": 70,
        "surprises": 2,
    },
    {
        "title": "Data Warehouse Migration",
        "description": "Move reporting from the on-prem warehouse to the cloud platform.",
        "tags": ["tech", "external", "scope"],
        "closed_days_ago": 110,
        "duration_days": 90,
        "surprises": 1,
    },
    {
        "title": "Mobile Launch",
        "description": "Ship the first version of the mobile app to both stores.",
        "tags": ["timeline", "people", "vendor"],
        "closed_days_ago": 70,
        "duration_days": 60,
        "surprises": 2,
    },
    {
        "title": "SSO Rollout",
        "description": "Roll out single sign-on across all internal tools with an identity vendor.",
        "tags": ["vendor", "external", "people"],
        "closed_days_ago": 30,
        "duration_days": 45,
        "surprises": 1,
    },
]

ACTIVE_PROJECT: ProjectSpec = {
    "title": "Q4 Platform Hardening",
    "description": "Reliability, observability and on-call improvements before the holiday freeze.",
    "tags": ["tech", "timeline"],
    "closed_days_ago": 0,
    "duration_days": 70,
    "surprises": 0,
}


def _persona_probability(email: str, truth: float, rng: random.Random) -> int:
    if email.startswith("ada"):
        p = truth * 100 + rng.gauss(0, 8)
    elif email.startswith("grace"):
        p = rng.uniform(82, 97) if truth > 0.45 else rng.uniform(3, 15)
    else:
        p = rng.uniform(38, 62)
    return int(max(0, min(100, round(p))))


def _outcome(truth: float, rng: random.Random) -> GradingOutcome:
    r = rng.random()
    if r < truth * 0.85:
        return GradingOutcome.yes
    if r < truth:
        return GradingOutcome.partial
    return GradingOutcome.no


def _pick_statements(tags: list[str], k: int, rng: random.Random) -> list[tuple[str, str]]:
    pool = [(tag, s) for tag in tags for s in STATEMENTS[tag]]
    rng.shuffle(pool)
    return pool[:k]


async def _ensure_users(db: AsyncSession, users: dict[str, uuid.UUID]) -> None:
    names = dict(USERS)
    for email, uid in users.items():
        await db.execute(
            insert(User)
            .values(id=uid, email=email, name=names.get(email, email.split("@")[0].title()))
            .on_conflict_do_nothing(index_elements=[User.id])
        )
    await db.flush()


async def _seed_closed_project(
    db: AsyncSession,
    ws: Workspace,
    spec: ProjectSpec,
    users: dict[str, uuid.UUID],
    rng: random.Random,
    now: datetime,
) -> None:
    ada = users["ada@demo.local"]
    closed_at = now - timedelta(days=spec["closed_days_ago"])
    started_at = closed_at - timedelta(days=spec["duration_days"])
    tags = list(spec["tags"])

    project = Project(
        workspace_id=ws.id,
        title=spec["title"],
        description=spec["description"],
        tags=tags,
        planned_start=started_at.date(),
        planned_end=closed_at.date(),
        status=ProjectStatus.closed,
        activated_at=started_at,
        closed_at=closed_at,
        closed_by=ada,
        created_by=ada,
        created_at=started_at - timedelta(days=7),
        updated_at=closed_at,
    )
    db.add(project)
    await db.flush()

    sealed_at = started_at - timedelta(days=1)
    sess = PremortemSession(
        project_id=project.id,
        workspace_id=ws.id,
        created_by=ada,
        facilitator_id=ada,
        phase=SessionPhase.sealed,
        phase_changed_at=sealed_at,
        sealed_at=sealed_at,
        fully_graded_at=closed_at,
        created_at=started_at - timedelta(days=6),
        updated_at=closed_at,
    )
    db.add(sess)
    await db.flush()
    for uid in users.values():
        db.add(SessionParticipant(session_id=sess.id, user_id=uid, added_by=ada))

    authors = list(users.values())
    for i, (tag, statement) in enumerate(_pick_statements(tags, 8, rng)):
        truth = rng.uniform(0.1, 0.9)
        base_impact = rng.randint(1, 5)
        risk = Risk(
            project_id=project.id,
            session_id=sess.id,
            workspace_id=ws.id,
            author_id=authors[i % len(authors)],
            statement=statement,
            submitted_statement=statement,
            tags=[tag],
            created_at=started_at - timedelta(days=5),
        )
        db.add(risk)
        await db.flush()
        probs: list[int] = []
        impacts: list[int] = []
        for email, uid in users.items():
            p = _persona_probability(email, truth, rng)
            impact = max(1, min(5, base_impact + rng.choice([-1, 0, 0, 1])))
            probs.append(p)
            impacts.append(impact)
            db.add(
                Vote(
                    risk_id=risk.id,
                    session_id=sess.id,
                    workspace_id=ws.id,
                    user_id=uid,
                    probability=p,
                    impact=impact,
                    created_at=sealed_at - timedelta(hours=2),
                )
            )
        agg = aggregate(probs, impacts)
        assert agg is not None
        risk.agg_vote_count = agg.vote_count
        risk.agg_mean_probability = Decimal(str(agg.mean_probability))
        risk.agg_median_probability = Decimal(str(agg.median_probability))
        risk.agg_probability_stddev = Decimal(str(agg.probability_stddev))
        risk.agg_mean_impact = Decimal(str(agg.mean_impact))
        risk.agg_risk_score = Decimal(str(agg.risk_score))
        db.add(
            Grading(
                risk_id=risk.id,
                project_id=project.id,
                graded_by=ada,
                outcome=_outcome(truth, rng),
                note="",
                created_at=closed_at,
            )
        )

    for statement, stags in rng.sample(SURPRISES, spec["surprises"]):
        surprise = Risk(
            project_id=project.id,
            session_id=None,
            workspace_id=ws.id,
            author_id=ada,
            origin=RiskOrigin.surprise,
            statement=statement,
            submitted_statement=statement,
            tags=stags,
            created_at=closed_at,
        )
        db.add(surprise)
        await db.flush()
        db.add(
            Grading(
                risk_id=surprise.id,
                project_id=project.id,
                graded_by=ada,
                outcome=GradingOutcome.yes,
                created_at=closed_at,
            )
        )
    await db.flush()


async def _seed_active_project(
    db: AsyncSession, ws: Workspace, users: dict[str, uuid.UUID], now: datetime
) -> None:
    ada, grace = users["ada@demo.local"], users["grace@demo.local"]
    project = Project(
        workspace_id=ws.id,
        title=ACTIVE_PROJECT["title"],
        description=ACTIVE_PROJECT["description"],
        tags=list(ACTIVE_PROJECT["tags"]),
        planned_start=(now - timedelta(days=10)).date(),
        planned_end=(now + timedelta(days=60)).date(),
        status=ProjectStatus.active,
        activated_at=now - timedelta(days=10),
        created_by=ada,
    )
    db.add(project)
    await db.flush()
    sess = PremortemSession(
        project_id=project.id, workspace_id=ws.id, created_by=ada, facilitator_id=ada
    )
    db.add(sess)
    await db.flush()
    for uid in users.values():
        db.add(SessionParticipant(session_id=sess.id, user_id=uid, added_by=ada))
    for author, statement in (
        (ada, "On-call rota has gaps over the holidays"),
        (grace, "Alerting thresholds are tuned for last year's traffic"),
    ):
        db.add(
            Risk(
                project_id=project.id,
                session_id=sess.id,
                workspace_id=ws.id,
                author_id=author,
                statement=statement,
                submitted_statement=statement,
            )
        )
    await db.flush()


async def seed_database(
    db: AsyncSession, users: dict[str, uuid.UUID], rng_seed: int = 42
) -> uuid.UUID:
    """Idempotent: returns the existing demo workspace id if it is already there."""
    existing = await db.scalar(select(Workspace).where(Workspace.slug == WORKSPACE_SLUG))
    if existing is not None:
        return existing.id
    rng = random.Random(rng_seed)
    now = datetime.now(UTC)
    await _ensure_users(db, users)

    ada = users["ada@demo.local"]
    ws = Workspace(name="Demo Team", slug=WORKSPACE_SLUG, created_by=ada)
    db.add(ws)
    await db.flush()
    for email, uid in users.items():
        role = WorkspaceRole.owner if uid == ada else WorkspaceRole.member
        db.add(WorkspaceMember(workspace_id=ws.id, user_id=uid, role=role))
    await db.flush()

    for spec in PROJECTS:
        await _seed_closed_project(db, ws, spec, users, rng, now)
    await _seed_active_project(db, ws, users, now)
    return ws.id


async def register_user(auth_url: str, email: str, name: str, password: str) -> uuid.UUID:
    """Create the account through the auth service; fall back to login if it already exists."""
    async with httpx.AsyncClient(base_url=auth_url, timeout=15) as client:
        r = await client.post(
            "/auth/register", json={"email": email, "name": name, "password": password}
        )
        if r.status_code == 409:
            r = await client.post("/auth/login", json={"email": email, "password": password})
        r.raise_for_status()
        return uuid.UUID(r.json()["user"]["id"])


async def main() -> None:
    auth_url = os.environ.get("AUTH_URL", "http://auth:8001")
    settings = get_settings()
    users: dict[str, uuid.UUID] = {}
    for email, name in USERS:
        users[email] = await register_user(auth_url, email, name, PASSWORD)
        print(f"user ready: {email}")

    engine = create_async_engine(settings.database_url)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as db:
        ws_id = await seed_database(db, users)
        await db.commit()
    await engine.dispose()

    print()
    print("Demo workspace ready: /w/" + str(ws_id))
    print(f"Sign in with any of: {', '.join(e for e, _ in USERS)}  (password: {PASSWORD})")
    print("Ada is the owner and facilitator; Grace is overconfident; Linus hedges.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except httpx.HTTPError as exc:  # pragma: no cover - CLI feedback only
        print(f"auth service unreachable or rejected the request: {exc}", file=sys.stderr)
        sys.exit(1)
