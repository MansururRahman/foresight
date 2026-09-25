import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import (
    Grading,
    GradingOutcome,
    PremortemSession,
    Project,
    ProjectStatus,
    Risk,
    SessionParticipant,
    User,
    Vote,
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
)


async def _seed(db):
    u = User(id=uuid.uuid4(), email=f"u-{uuid.uuid4().hex[:6]}@demo.local", name="U")
    db.add(u)
    await db.flush()
    ws = Workspace(name="W", slug=f"w-{uuid.uuid4().hex[:6]}", created_by=u.id)
    db.add(ws)
    await db.flush()
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=u.id, role=WorkspaceRole.owner))
    p = Project(workspace_id=ws.id, title="P", description="d", tags=["vendor"], created_by=u.id)
    db.add(p)
    await db.flush()
    s = PremortemSession(project_id=p.id, workspace_id=ws.id, created_by=u.id, facilitator_id=u.id)
    db.add(s)
    await db.flush()
    db.add(SessionParticipant(session_id=s.id, user_id=u.id, added_by=u.id))
    r = Risk(
        project_id=p.id,
        session_id=s.id,
        workspace_id=ws.id,
        author_id=u.id,
        statement="Vendor late",
        submitted_statement="Vendor late",
    )
    db.add(r)
    await db.flush()
    return u, ws, p, s, r


async def test_graded_predictions_view_row(db_session):
    u, ws, p, s, r = await _seed(db_session)
    db_session.add(
        Vote(
            risk_id=r.id,
            session_id=s.id,
            workspace_id=ws.id,
            user_id=u.id,
            probability=80,
            impact=3,
        )
    )
    db_session.add(
        Grading(risk_id=r.id, project_id=p.id, graded_by=u.id, outcome=GradingOutcome.partial)
    )
    await db_session.flush()
    rows = (
        await db_session.execute(
            text("select p, o, tags, probability from graded_predictions where risk_id = :rid"),
            {"rid": r.id},
        )
    ).all()
    assert len(rows) == 1
    assert float(rows[0].p) == pytest.approx(0.8)
    assert float(rows[0].o) == 0.5
    assert rows[0].probability == 80
    assert list(rows[0].tags) == ["vendor"]  # inherited from the project: the risk has no tags


async def test_view_excludes_duplicate_risks(db_session):
    u, ws, p, s, r = await _seed(db_session)
    dup = Risk(
        project_id=p.id,
        session_id=s.id,
        workspace_id=ws.id,
        author_id=u.id,
        statement="Vendor late (dup)",
        submitted_statement="Vendor late (dup)",
        duplicate_of=r.id,
    )
    db_session.add(dup)
    await db_session.flush()
    db_session.add(
        Vote(
            risk_id=dup.id,
            session_id=s.id,
            workspace_id=ws.id,
            user_id=u.id,
            probability=50,
            impact=3,
        )
    )
    db_session.add(
        Grading(risk_id=dup.id, project_id=p.id, graded_by=u.id, outcome=GradingOutcome.yes)
    )
    await db_session.flush()
    n = await db_session.scalar(
        text("select count(*) from graded_predictions where risk_id = :rid"), {"rid": dup.id}
    )
    assert n == 0


async def test_vote_probability_range_enforced(db_session):
    u, ws, p, s, r = await _seed(db_session)
    db_session.add(
        Vote(
            risk_id=r.id,
            session_id=s.id,
            workspace_id=ws.id,
            user_id=u.id,
            probability=101,
            impact=3,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_one_vote_per_user_per_risk(db_session):
    u, ws, p, s, r = await _seed(db_session)
    db_session.add(
        Vote(
            risk_id=r.id,
            session_id=s.id,
            workspace_id=ws.id,
            user_id=u.id,
            probability=10,
            impact=1,
        )
    )
    await db_session.flush()
    db_session.add(
        Vote(
            risk_id=r.id,
            session_id=s.id,
            workspace_id=ws.id,
            user_id=u.id,
            probability=20,
            impact=1,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_project_closed_requires_closed_at(db_session):
    u, ws, p, s, r = await _seed(db_session)
    p.status = ProjectStatus.closed
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_surprise_requires_null_session(db_session):
    u, ws, p, s, r = await _seed(db_session)
    from app.models import RiskOrigin

    bad = Risk(
        project_id=p.id,
        session_id=s.id,
        workspace_id=ws.id,
        author_id=u.id,
        origin=RiskOrigin.surprise,
        statement="Legal blocked",
        submitted_statement="Legal blocked",
    )
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_search_text_is_generated(db_session):
    u, ws, p, s, r = await _seed(db_session)
    val = await db_session.scalar(
        text("select search_text from projects where id = :pid"), {"pid": p.id}
    )
    assert val == "P d"
