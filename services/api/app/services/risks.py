"""Risk statements: private collection, facilitator merge, duplicate handling, adoption."""

import uuid
from collections.abc import Sequence
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.deps import not_found
from app.models import (
    Grading,
    PremortemSession,
    Project,
    Risk,
    RiskOrigin,
    SessionPhase,
    User,
    Vote,
    WorkspaceMember,
)
from app.schemas.common import UserRef
from app.schemas.risk import (
    Aggregates,
    GradingOut,
    MergedFrom,
    MyVote,
    RiskAdopt,
    RiskList,
    RiskOut,
    RiskPatch,
    SubmissionCount,
)

AuthorMode = Literal["all", "self", "none"]
MAX_DUP_DEPTH = 50


def aggregates_of(risk: Risk) -> Aggregates | None:
    if risk.agg_vote_count is None or not risk.agg_vote_count:
        return None
    stddev = float(risk.agg_probability_stddev or 0)
    return Aggregates(
        vote_count=risk.agg_vote_count,
        mean_probability=float(risk.agg_mean_probability or 0),
        median_probability=float(risk.agg_median_probability or 0),
        probability_stddev=stddev,
        agreement=max(0.0, min(1.0, 1 - stddev / 50)),
        mean_impact=float(risk.agg_mean_impact or 0),
        risk_score=float(risk.agg_risk_score or 0),
    )


async def build_outs(
    db: AsyncSession,
    risks: Sequence[Risk],
    viewer: User,
    *,
    author_mode: AuthorMode,
    with_merged: bool = False,
) -> list[RiskOut]:
    if not risks:
        return []
    ids = [r.id for r in risks]

    authors: dict[uuid.UUID, User] = {}
    if author_mode != "none":
        wanted = {r.author_id for r in risks}
        rows = await db.execute(select(User).where(User.id.in_(wanted)))
        authors = {u.id: u for u in rows.scalars().all()}

    votes_rows = await db.execute(
        select(Vote).where(Vote.risk_id.in_(ids), Vote.user_id == viewer.id)
    )
    my_votes = {v.risk_id: v for v in votes_rows.scalars().all()}

    grading_rows = await db.execute(
        select(Grading, User)
        .join(User, User.id == Grading.graded_by)
        .where(Grading.risk_id.in_(ids))
    )
    gradings = {g.risk_id: (g, u) for g, u in grading_rows.all()}

    merged: dict[uuid.UUID, list[MergedFrom]] = {}
    if with_merged:
        child_rows = await db.execute(
            select(Risk).where(Risk.duplicate_of.in_(ids)).order_by(Risk.created_at)
        )
        for child in child_rows.scalars().all():
            assert child.duplicate_of is not None
            merged.setdefault(child.duplicate_of, []).append(
                MergedFrom(id=child.id, statement=child.statement)
            )

    out: list[RiskOut] = []
    for r in risks:
        author: UserRef | None = None
        if author_mode == "all" or (author_mode == "self" and r.author_id == viewer.id):
            a = authors.get(r.author_id)
            author = UserRef.model_validate(a, from_attributes=True) if a else None
        v = my_votes.get(r.id)
        g = gradings.get(r.id)
        out.append(
            RiskOut(
                id=r.id,
                session_id=r.session_id,
                project_id=r.project_id,
                statement=r.statement,
                tags=list(r.tags),
                origin=r.origin,
                duplicate_of=r.duplicate_of,
                source_risk_id=r.source_risk_id,
                author=author,
                created_at=r.created_at,
                updated_at=r.updated_at,
                aggregates=aggregates_of(r),
                merged_from=merged.get(r.id, []),
                my_vote=MyVote(probability=v.probability, impact=v.impact) if v else None,
                grading=(
                    GradingOut(
                        outcome=g[0].outcome,
                        note=g[0].note,
                        graded_by=UserRef.model_validate(g[1], from_attributes=True),
                        updated_at=g[0].updated_at,
                    )
                    if g
                    else None
                ),
            )
        )
    return out


async def build_one(db: AsyncSession, risk: Risk, viewer: User, author_mode: AuthorMode) -> RiskOut:
    return (await build_outs(db, [risk], viewer, author_mode=author_mode, with_merged=True))[0]


async def load_for_member(
    db: AsyncSession, risk_id: uuid.UUID, user: User
) -> tuple[Risk, PremortemSession | None, Project, WorkspaceMember]:
    risk = await db.get(Risk, risk_id)
    if risk is None:
        raise not_found("Risk")
    member = await db.get(WorkspaceMember, (risk.workspace_id, user.id))
    if member is None:
        raise not_found("Risk")
    project = await db.get(Project, risk.project_id)
    assert project is not None
    sess = await db.get(PremortemSession, risk.session_id) if risk.session_id else None
    return risk, sess, project, member


async def _submission_counts(db: AsyncSession, session_id: uuid.UUID) -> list[SubmissionCount]:
    rows = await db.execute(
        select(User, func.count(Risk.id))
        .join(Risk, Risk.author_id == User.id)
        .where(Risk.session_id == session_id)
        .group_by(User.id)
        .order_by(User.name)
    )
    return [
        SubmissionCount(user=UserRef.model_validate(u, from_attributes=True), count=int(n))
        for u, n in rows.all()
    ]


async def visible_list(
    db: AsyncSession,
    sess: PremortemSession,
    user: User,
    *,
    is_fac: bool,
    is_part: bool,
) -> RiskList:
    base = select(Risk).where(Risk.session_id == sess.id).order_by(Risk.created_at, Risk.id)
    if sess.phase == SessionPhase.collect:
        if not is_part:
            raise AppError(403, "not_participant", "Only participants can see this session")
        rows = await db.execute(base.where(Risk.author_id == user.id))
        items = await build_outs(db, rows.scalars().all(), user, author_mode="all")
        counts = await _submission_counts(db, sess.id) if is_fac else None
        return RiskList(phase=sess.phase, items=items, submission_counts=counts)
    if sess.phase == SessionPhase.merge:
        if not is_fac:
            raise AppError(403, "phase_not_visible", "Risks are being merged by the facilitator")
        rows = await db.execute(base)
        items = await build_outs(
            db, rows.scalars().all(), user, author_mode="all", with_merged=True
        )
        return RiskList(
            phase=sess.phase, items=items, submission_counts=await _submission_counts(db, sess.id)
        )
    if sess.phase == SessionPhase.vote:
        if not is_part:
            raise AppError(403, "not_participant", "Only participants can see this session")
        rows = await db.execute(base.where(Risk.duplicate_of.is_(None)))
        items = await build_outs(db, rows.scalars().all(), user, author_mode="none")
        return RiskList(phase=sess.phase, items=items)
    rows = await db.execute(base.where(Risk.duplicate_of.is_(None)))
    items = await build_outs(db, rows.scalars().all(), user, author_mode="self", with_merged=True)
    return RiskList(phase=sess.phase, items=items)


async def create(
    db: AsyncSession, sess: PremortemSession, user: User, *, is_part: bool, statement: str
) -> RiskOut:
    if sess.phase != SessionPhase.collect:
        raise AppError(409, "phase_locked", "Risks can only be submitted during collection")
    if not is_part:
        raise AppError(403, "not_participant", "Only participants can submit risks")
    project = await db.get(Project, sess.project_id)
    if project is not None and project.archived_at is not None:
        raise AppError(409, "project_archived", "This project is archived; unarchive it first")
    risk = Risk(
        project_id=sess.project_id,
        session_id=sess.id,
        workspace_id=sess.workspace_id,
        author_id=user.id,
        statement=statement,
        submitted_statement=statement,
    )
    db.add(risk)
    await db.commit()
    return await build_one(db, risk, user, "all")


async def resolve_duplicate_root(db: AsyncSession, risk: Risk, target_id: uuid.UUID) -> uuid.UUID:
    """Follow duplicate_of links from target to the canonical root; reject bad targets."""
    if target_id == risk.id:
        raise AppError(400, "invalid_duplicate", "A risk cannot duplicate itself")
    current = await db.get(Risk, target_id)
    if current is None or current.session_id != risk.session_id:
        raise AppError(400, "invalid_duplicate", "Target risk is not in this session")
    seen: set[uuid.UUID] = set()
    for _ in range(MAX_DUP_DEPTH):
        if current.id == risk.id:
            raise AppError(400, "invalid_duplicate", "Marking this would create a cycle")
        if current.duplicate_of is None:
            return current.id
        if current.id in seen:
            break
        seen.add(current.id)
        nxt = await db.get(Risk, current.duplicate_of)
        if nxt is None:
            return current.id
        current = nxt
    raise AppError(400, "invalid_duplicate", "Duplicate chain is too deep")


async def patch(
    db: AsyncSession,
    sess: PremortemSession,
    risk: Risk,
    user: User,
    *,
    is_fac: bool,
    data: RiskPatch,
) -> RiskOut:
    if sess.phase == SessionPhase.collect:
        if risk.author_id != user.id:
            raise not_found("Risk")
        if "tags" in data.model_fields_set or "duplicate_of" in data.model_fields_set:
            raise AppError(
                400, "field_locked", "Only the statement can be edited during collection"
            )
        if data.statement is not None:
            risk.statement = data.statement
            risk.submitted_statement = data.statement
    elif sess.phase == SessionPhase.merge:
        if not is_fac:
            raise AppError(
                403, "facilitator_required", "Only the facilitator can edit during merge"
            )
        if data.statement is not None:
            risk.statement = data.statement
        if data.tags is not None:
            risk.tags = data.tags
        if "duplicate_of" in data.model_fields_set:
            if data.duplicate_of is None:
                risk.duplicate_of = None
            else:
                root = await resolve_duplicate_root(db, risk, data.duplicate_of)
                risk.duplicate_of = root
                # Keep the forest flat: anything pointing at this risk now points at the root.
                children = await db.execute(select(Risk).where(Risk.duplicate_of == risk.id))
                for child in children.scalars().all():
                    child.duplicate_of = root
    else:
        raise AppError(409, "phase_locked", "Risks are frozen once voting starts")
    await db.commit()
    await db.refresh(risk)
    return await build_one(db, risk, user, "all" if is_fac else "self")


async def delete(
    db: AsyncSession, sess: PremortemSession, risk: Risk, user: User, *, is_fac: bool
) -> None:
    if sess.phase == SessionPhase.collect:
        if risk.author_id != user.id:
            raise not_found("Risk")
    elif sess.phase == SessionPhase.merge:
        if not is_fac:
            raise AppError(
                403, "facilitator_required", "Only the facilitator can delete during merge"
            )
    else:
        raise AppError(409, "phase_locked", "Risks are frozen once voting starts")
    await db.delete(risk)
    await db.commit()


async def adopt(
    db: AsyncSession, sess: PremortemSession, user: User, *, is_fac: bool, data: RiskAdopt
) -> RiskOut:
    if sess.phase != SessionPhase.merge:
        raise AppError(409, "phase_locked", "Suggestions can only be adopted during merge")
    if not is_fac:
        raise AppError(403, "facilitator_required", "Only the facilitator can adopt suggestions")
    source = await db.get(Risk, data.source_risk_id)
    graded = (
        await db.scalar(select(Grading.id).where(Grading.risk_id == data.source_risk_id))
        if source is not None
        else None
    )
    if (
        source is None
        or source.workspace_id != sess.workspace_id
        or source.duplicate_of is not None
        or graded is None
    ):
        raise not_found("Source risk")
    statement = data.statement or source.statement
    risk = Risk(
        project_id=sess.project_id,
        session_id=sess.id,
        workspace_id=sess.workspace_id,
        author_id=user.id,
        origin=RiskOrigin.suggestion,
        statement=statement,
        submitted_statement=statement,
        tags=data.tags if data.tags is not None else list(source.tags),
        source_risk_id=source.id,
    )
    db.add(risk)
    await db.commit()
    return await build_one(db, risk, user, "all")
