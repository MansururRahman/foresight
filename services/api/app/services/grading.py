"""Close-out: grading canonical risks against reality, recording surprises, project report."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.deps import is_admin
from app.models import (
    OUTCOME_VALUE,
    Grading,
    GradingOutcome,
    PremortemSession,
    Project,
    ProjectStatus,
    Risk,
    RiskOrigin,
    SessionPhase,
    User,
    Vote,
    WorkspaceMember,
)
from app.schemas.grading import (
    CloseoutOut,
    GradingIn,
    PossibleDuplicate,
    ProjectReport,
    ReportRisk,
    ReportSummary,
    ReportSurprise,
    SurpriseCreate,
)
from app.schemas.risk import RiskOut
from app.services import projects as projects_service
from app.services import risks as risks_service
from app.services import sessions as sessions_service

DUPLICATE_SIMILARITY = 0.5


async def load_session(db: AsyncSession, project: Project) -> PremortemSession | None:
    return await db.scalar(
        select(PremortemSession).where(PremortemSession.project_id == project.id)
    )


def _can_manage(
    project: Project, sess: PremortemSession | None, member: WorkspaceMember, user: User
) -> bool:
    if is_admin(member):
        return True
    if sess is not None:
        return sess.facilitator_id == user.id
    return project.created_by == user.id


def require_grader(
    project: Project, sess: PremortemSession | None, member: WorkspaceMember, user: User
) -> PremortemSession:
    if sess is None:
        raise AppError(409, "no_session", "This project has no pre-mortem session to grade")
    if not _can_manage(project, sess, member, user):
        raise AppError(403, "facilitator_required", "Only the facilitator can grade risks")
    if sess.phase != SessionPhase.sealed:
        raise AppError(409, "session_not_sealed", "Seal the session before grading")
    if project.status == ProjectStatus.planning:
        raise AppError(409, "project_not_started", "Activate the project before grading")
    return sess


async def _canonical_risks(db: AsyncSession, sess: PremortemSession) -> list[Risk]:
    rows = await db.execute(
        select(Risk)
        .where(Risk.session_id == sess.id, Risk.duplicate_of.is_(None))
        .order_by(Risk.agg_risk_score.desc().nullslast(), Risk.created_at)
    )
    return list(rows.scalars().all())


async def _surprises(db: AsyncSession, project: Project) -> list[Risk]:
    rows = await db.execute(
        select(Risk)
        .where(Risk.project_id == project.id, Risk.origin == RiskOrigin.surprise)
        .order_by(Risk.created_at)
    )
    return list(rows.scalars().all())


async def _ungraded(db: AsyncSession, sess: PremortemSession) -> int:
    n = await db.scalar(
        select(func.count())
        .select_from(Risk)
        .outerjoin(Grading, Grading.risk_id == Risk.id)
        .where(Risk.session_id == sess.id, Risk.duplicate_of.is_(None), Grading.id.is_(None))
    )
    return int(n or 0)


async def _refresh_fully_graded(db: AsyncSession, sess: PremortemSession) -> None:
    ungraded = await _ungraded(db, sess)
    sess.fully_graded_at = None if ungraded else (sess.fully_graded_at or datetime.now(UTC))


async def _possible_duplicates(
    db: AsyncSession, project: Project, sess: PremortemSession | None
) -> list[PossibleDuplicate]:
    if sess is None:
        return []
    rows = await db.execute(
        text(
            """
            SELECT s.id AS surprise_id, r.id AS risk_id,
                   similarity(lower(s.statement), lower(r.statement)) AS sim
            FROM risks s
            JOIN risks r ON r.session_id = :sid AND r.duplicate_of IS NULL
            WHERE s.project_id = :pid AND s.origin = 'surprise'
              AND similarity(lower(s.statement), lower(r.statement)) > :threshold
            ORDER BY sim DESC
            """
        ),
        {"sid": sess.id, "pid": project.id, "threshold": DUPLICATE_SIMILARITY},
    )
    return [
        PossibleDuplicate(surprise_id=s, risk_id=r, similarity=round(float(sim), 3))
        for s, r, sim in rows.all()
    ]


async def closeout(
    db: AsyncSession, project: Project, member: WorkspaceMember, user: User
) -> CloseoutOut:
    sess = await load_session(db, project)
    risks: list[RiskOut] = []
    ungraded = 0
    session_out = None
    if sess is not None:
        session_out = await sessions_service.build_out(db, sess, user, member)
        if sess.phase == SessionPhase.sealed:
            risks = await risks_service.build_outs(
                db, await _canonical_risks(db, sess), user, author_mode="self", with_merged=True
            )
            ungraded = await _ungraded(db, sess)
    surprises = await risks_service.build_outs(
        db, await _surprises(db, project), user, author_mode="all"
    )
    return CloseoutOut(
        project=await projects_service.load_out(db, project.id),
        session=session_out,
        risks=risks,
        surprises=surprises,
        ungraded_count=ungraded,
        possible_duplicates=await _possible_duplicates(db, project, sess),
    )


async def put_gradings(
    db: AsyncSession,
    project: Project,
    member: WorkspaceMember,
    user: User,
    items: list[GradingIn],
) -> CloseoutOut:
    sess = await load_session(db, project)
    sess = require_grader(project, sess, member, user)
    canonical_ids = {r.id for r in await _canonical_risks(db, sess)}
    unknown = [str(g.risk_id) for g in items if g.risk_id not in canonical_ids]
    if unknown:
        raise AppError(
            400,
            "unknown_risk",
            "Some risk ids are not canonical risks of this project",
            {"risk_ids": unknown},
        )
    latest: dict[uuid.UUID, GradingIn] = {g.risk_id: g for g in items}
    for g in latest.values():
        stmt = (
            insert(Grading)
            .values(
                id=uuid.uuid4(),
                risk_id=g.risk_id,
                project_id=project.id,
                graded_by=user.id,
                outcome=g.outcome,
                note=g.note,
            )
            .on_conflict_do_update(
                index_elements=[Grading.risk_id],
                set_={
                    "outcome": g.outcome,
                    "note": g.note,
                    "graded_by": user.id,
                    "updated_at": func.now(),
                },
            )
        )
        await db.execute(stmt)
    await _refresh_fully_graded(db, sess)
    await db.commit()
    return await closeout(db, project, member, user)


async def delete_grading(
    db: AsyncSession, project: Project, member: WorkspaceMember, user: User, risk_id: uuid.UUID
) -> None:
    sess = await load_session(db, project)
    sess = require_grader(project, sess, member, user)
    grading = await db.scalar(select(Grading).where(Grading.risk_id == risk_id))
    if grading is None or grading.project_id != project.id:
        raise AppError(404, "not_found", "Grading not found")
    await db.delete(grading)
    await db.flush()
    await _refresh_fully_graded(db, sess)
    await db.commit()


def require_surprise_manager(
    project: Project, sess: PremortemSession | None, member: WorkspaceMember, user: User
) -> None:
    if not _can_manage(project, sess, member, user):
        raise AppError(403, "facilitator_required", "Only the facilitator can record surprises")
    if project.status == ProjectStatus.planning:
        raise AppError(
            409, "project_not_started", "Activate the project before recording surprises"
        )


async def add_surprise(
    db: AsyncSession, project: Project, member: WorkspaceMember, user: User, data: SurpriseCreate
) -> RiskOut:
    sess = await load_session(db, project)
    require_surprise_manager(project, sess, member, user)
    risk = Risk(
        project_id=project.id,
        session_id=None,
        workspace_id=project.workspace_id,
        author_id=user.id,
        origin=RiskOrigin.surprise,
        statement=data.statement,
        submitted_statement=data.statement,
        tags=data.tags,
    )
    db.add(risk)
    await db.flush()
    db.add(
        Grading(
            risk_id=risk.id, project_id=project.id, graded_by=user.id, outcome=GradingOutcome.yes
        )
    )
    await db.commit()
    return await risks_service.build_one(db, risk, user, "all")


async def patch_surprise(
    db: AsyncSession,
    project: Project,
    member: WorkspaceMember,
    user: User,
    risk: Risk,
    *,
    statement: str | None,
    tags: list[str] | None,
) -> RiskOut:
    sess = await load_session(db, project)
    require_surprise_manager(project, sess, member, user)
    if statement is not None:
        risk.statement = statement
    if tags is not None:
        risk.tags = tags
    await db.commit()
    return await risks_service.build_one(db, risk, user, "all")


async def delete_surprise(
    db: AsyncSession, project: Project, member: WorkspaceMember, user: User, risk: Risk
) -> None:
    sess = await load_session(db, project)
    require_surprise_manager(project, sess, member, user)
    await db.delete(risk)
    await db.commit()


async def report(
    db: AsyncSession, project: Project, member: WorkspaceMember, user: User
) -> ProjectReport:
    sess = await load_session(db, project)
    session_out = await sessions_service.build_out(db, sess, user, member) if sess else None
    canonical = await _canonical_risks(db, sess) if sess else []
    gradings: dict[uuid.UUID, Grading] = {}
    if canonical:
        grading_rows = await db.execute(
            select(Grading).where(Grading.risk_id.in_([r.id for r in canonical]))
        )
        gradings = {g.risk_id: g for g in grading_rows.scalars().all()}

    votes = (
        (await db.execute(select(Vote).where(Vote.session_id == sess.id))).scalars().all()
        if sess
        else []
    )
    voters = {v.user_id for v in votes}
    sq_errors: list[float] = []
    for v in votes:
        g = gradings.get(v.risk_id)
        if g is not None:
            sq_errors.append((v.probability / 100 - OUTCOME_VALUE[g.outcome]) ** 2)

    risks_out: list[ReportRisk] = []
    expected = 0.0
    actual = 0.0
    for r in canonical:
        agg = risks_service.aggregates_of(r)
        mean_p = agg.mean_probability / 100 if agg else None
        g = gradings.get(r.id)
        o = OUTCOME_VALUE[g.outcome] if g else None
        if mean_p is not None:
            expected += mean_p
        if o is not None:
            actual += o
        risks_out.append(
            ReportRisk(
                risk_id=r.id,
                statement=r.statement,
                tags=list(r.tags),
                mean_predicted=agg.mean_probability if agg else None,
                agreement=agg.agreement if agg else None,
                mean_impact=agg.mean_impact if agg else None,
                outcome=g.outcome if g else None,
                miss=(o - mean_p) if (o is not None and mean_p is not None) else None,
                note=g.note if g else "",
            )
        )
    surprises = [
        ReportSurprise(risk_id=s.id, statement=s.statement, tags=list(s.tags))
        for s in await _surprises(db, project)
    ]
    misses = sorted(
        (x for x in risks_out if x.miss is not None), key=lambda x: abs(x.miss or 0), reverse=True
    )
    return ProjectReport(
        project=await projects_service.load_out(db, project.id),
        session=session_out,
        summary=ReportSummary(
            n_canonical=len(canonical),
            n_graded=len(gradings),
            n_voters=len(voters),
            expected_materialized=round(expected, 4),
            actual_materialized=round(actual, 4),
            project_brier=round(sum(sq_errors) / len(sq_errors), 6) if sq_errors else None,
            n_predictions=len(sq_errors),
        ),
        risks=risks_out,
        surprises=surprises,
        biggest_misses=misses[:3],
    )
