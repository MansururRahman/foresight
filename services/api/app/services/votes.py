"""Hidden voting, seal-time aggregation and sealed results."""

import uuid
from collections.abc import Sequence
from decimal import Decimal
from statistics import fmean, median, pstdev

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import (
    PremortemSession,
    Risk,
    SessionParticipant,
    SessionPhase,
    User,
    Vote,
    WorkspaceMember,
)
from app.schemas.common import UserRef
from app.schemas.risk import Aggregates
from app.schemas.vote import (
    MyVoteItem,
    MyVotes,
    Participation,
    ResultRisk,
    ResultsOut,
    VoteIn,
)
from app.services import risks as risks_service
from app.services import sessions as sessions_service

HISTOGRAM_BUCKETS = 10


def aggregate(probabilities: Sequence[int], impacts: Sequence[int]) -> Aggregates | None:
    """Pure seal-time aggregation for one risk. None when there are no votes."""
    if not probabilities:
        return None
    mean_p = fmean(probabilities)
    stddev = pstdev(probabilities) if len(probabilities) > 1 else 0.0
    mean_impact = fmean(impacts)
    return Aggregates(
        vote_count=len(probabilities),
        mean_probability=round(mean_p, 2),
        median_probability=round(float(median(probabilities)), 2),
        probability_stddev=round(stddev, 2),
        agreement=max(0.0, min(1.0, round(1 - stddev / 50, 4))),
        mean_impact=round(mean_impact, 2),
        risk_score=round(mean_p / 100 * mean_impact, 3),
    )


def histogram(probabilities: Sequence[int]) -> list[int]:
    buckets = [0] * HISTOGRAM_BUCKETS
    for p in probabilities:
        buckets[min(p // 10, HISTOGRAM_BUCKETS - 1)] += 1
    return buckets


async def _canonical_ids(db: AsyncSession, session_id: uuid.UUID) -> set[uuid.UUID]:
    rows = await db.execute(
        select(Risk.id).where(Risk.session_id == session_id, Risk.duplicate_of.is_(None))
    )
    return {row[0] for row in rows.all()}


async def my_votes(db: AsyncSession, sess: PremortemSession, user: User) -> MyVotes:
    rows = await db.execute(
        select(Vote)
        .where(Vote.session_id == sess.id, Vote.user_id == user.id)
        .order_by(Vote.created_at)
    )
    required = (
        await sessions_service.canonical_count(db, sess.id)
        if sess.phase in (SessionPhase.vote, SessionPhase.sealed)
        else 0
    )
    return MyVotes(
        items=[
            MyVoteItem(
                risk_id=v.risk_id,
                probability=v.probability,
                impact=v.impact,
                updated_at=v.updated_at,
            )
            for v in rows.scalars().all()
        ],
        required=required,
    )


async def put_votes(
    db: AsyncSession, sess: PremortemSession, user: User, votes: list[VoteIn]
) -> MyVotes:
    if sess.phase != SessionPhase.vote:
        raise AppError(409, "phase_locked", "Votes can only be cast during the vote phase")
    canonical = await _canonical_ids(db, sess.id)
    unknown = [str(v.risk_id) for v in votes if v.risk_id not in canonical]
    if unknown:
        raise AppError(
            400,
            "unknown_risk",
            "Some risk ids are not canonical risks of this session",
            {"risk_ids": unknown},
        )
    # Last write wins within one request for duplicate risk ids.
    latest: dict[uuid.UUID, VoteIn] = {v.risk_id: v for v in votes}
    for v in latest.values():
        stmt = (
            insert(Vote)
            .values(
                id=uuid.uuid4(),
                risk_id=v.risk_id,
                session_id=sess.id,
                workspace_id=sess.workspace_id,
                user_id=user.id,
                probability=v.probability,
                impact=v.impact,
            )
            .on_conflict_do_update(
                constraint="votes_risk_user_key",
                set_={"probability": v.probability, "impact": v.impact, "updated_at": func.now()},
            )
        )
        await db.execute(stmt)
    await db.commit()
    return await my_votes(db, sess, user)


async def seal(db: AsyncSession, sess: PremortemSession) -> list[UserRef]:
    """Freeze aggregates on every canonical risk. Runs inside the transition's transaction.
    Returns participants who voted on fewer risks than there are canonical risks."""
    risks = (
        (
            await db.execute(
                select(Risk)
                .where(Risk.session_id == sess.id, Risk.duplicate_of.is_(None))
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    votes = (await db.execute(select(Vote).where(Vote.session_id == sess.id))).scalars().all()
    if not votes:
        raise AppError(409, "no_votes", "At least one vote is required before sealing")

    by_risk: dict[uuid.UUID, list[Vote]] = {}
    by_user: dict[uuid.UUID, int] = {}
    for v in votes:
        by_risk.setdefault(v.risk_id, []).append(v)
        by_user[v.user_id] = by_user.get(v.user_id, 0) + 1

    for r in risks:
        agg = aggregate(
            [v.probability for v in by_risk.get(r.id, [])],
            [v.impact for v in by_risk.get(r.id, [])],
        )
        if agg is None:
            r.agg_vote_count = 0
            r.agg_mean_probability = None
            r.agg_median_probability = None
            r.agg_probability_stddev = None
            r.agg_mean_impact = None
            r.agg_risk_score = None
        else:
            r.agg_vote_count = agg.vote_count
            r.agg_mean_probability = Decimal(str(agg.mean_probability))
            r.agg_median_probability = Decimal(str(agg.median_probability))
            r.agg_probability_stddev = Decimal(str(agg.probability_stddev))
            r.agg_mean_impact = Decimal(str(agg.mean_impact))
            r.agg_risk_score = Decimal(str(agg.risk_score))
    await db.flush()

    participants = await db.execute(
        select(User)
        .join(SessionParticipant, SessionParticipant.user_id == User.id)
        .where(SessionParticipant.session_id == sess.id)
        .order_by(SessionParticipant.created_at)
    )
    canonical = len(risks)
    return [
        UserRef.model_validate(p, from_attributes=True)
        for p in participants.scalars().all()
        if by_user.get(p.id, 0) < canonical
    ]


async def results(
    db: AsyncSession, sess: PremortemSession, user: User, member: WorkspaceMember
) -> ResultsOut:
    if sess.phase != SessionPhase.sealed:
        raise AppError(409, "not_sealed", "Results are available once the session is sealed")
    risks = (
        (
            await db.execute(
                select(Risk)
                .where(Risk.session_id == sess.id, Risk.duplicate_of.is_(None))
                .order_by(Risk.agg_risk_score.desc().nullslast(), Risk.created_at)
            )
        )
        .scalars()
        .all()
    )
    outs = await risks_service.build_outs(db, risks, user, author_mode="self", with_merged=True)
    votes = (await db.execute(select(Vote).where(Vote.session_id == sess.id))).scalars().all()
    probs_by_risk: dict[uuid.UUID, list[int]] = {}
    by_user: dict[uuid.UUID, int] = {}
    for v in votes:
        probs_by_risk.setdefault(v.risk_id, []).append(v.probability)
        by_user[v.user_id] = by_user.get(v.user_id, 0) + 1

    participant_ids = [
        row[0]
        for row in (
            await db.execute(
                select(SessionParticipant.user_id).where(SessionParticipant.session_id == sess.id)
            )
        ).all()
    ]
    canonical = len(risks)
    complete = sum(1 for pid in participant_ids if by_user.get(pid, 0) >= canonical and canonical)
    none = sum(1 for pid in participant_ids if by_user.get(pid, 0) == 0)
    partial = len(participant_ids) - complete - none

    return ResultsOut(
        session=await sessions_service.build_out(db, sess, user, member),
        risks=[
            ResultRisk(**o.model_dump(), histogram=histogram(probs_by_risk.get(o.id, [])))
            for o in outs
        ],
        participation=Participation(
            participants=len(participant_ids),
            voters_complete=complete,
            voters_partial=partial,
            voters_none=none,
        ),
    )
