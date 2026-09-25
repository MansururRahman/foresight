"""Pre-mortem sessions: lifecycle, participants, phase transitions."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.deps import is_admin, not_found
from app.models import (
    PremortemSession,
    Project,
    ProjectStatus,
    Risk,
    SessionParticipant,
    SessionPhase,
    User,
    Vote,
    WorkspaceMember,
)
from app.schemas.common import UserRef
from app.schemas.session import SessionCounts, SessionMe, SessionOut, SessionTransitionResult
from app.services import votes as votes_service

NEXT_PHASE: dict[SessionPhase, SessionPhase] = {
    SessionPhase.collect: SessionPhase.merge,
    SessionPhase.merge: SessionPhase.vote,
    SessionPhase.vote: SessionPhase.sealed,
}


def _now() -> datetime:
    return datetime.now(UTC)


async def load_for_member(
    db: AsyncSession, session_id: uuid.UUID, user: User
) -> tuple[PremortemSession, Project, WorkspaceMember]:
    sess = await db.get(PremortemSession, session_id)
    if sess is None:
        raise not_found("Session")
    member = await db.get(WorkspaceMember, (sess.workspace_id, user.id))
    if member is None:
        raise not_found("Session")
    project = await db.get(Project, sess.project_id)
    assert project is not None
    return sess, project, member


def is_facilitator(sess: PremortemSession, member: WorkspaceMember, user: User) -> bool:
    return sess.facilitator_id == user.id or is_admin(member)


def require_facilitator(sess: PremortemSession, member: WorkspaceMember, user: User) -> None:
    if not is_facilitator(sess, member, user):
        raise AppError(403, "facilitator_required", "Only the facilitator can do this")


async def is_participant(db: AsyncSession, sess: PremortemSession, user: User) -> bool:
    return await db.get(SessionParticipant, (sess.id, user.id)) is not None


async def canonical_count(db: AsyncSession, session_id: uuid.UUID) -> int:
    n = await db.scalar(
        select(func.count())
        .select_from(Risk)
        .where(Risk.session_id == session_id, Risk.duplicate_of.is_(None))
    )
    return int(n or 0)


async def _participants(db: AsyncSession, session_id: uuid.UUID) -> list[User]:
    rows = await db.execute(
        select(User)
        .join(SessionParticipant, SessionParticipant.user_id == User.id)
        .where(SessionParticipant.session_id == session_id)
        .order_by(SessionParticipant.created_at, User.id)
    )
    return list(rows.scalars().all())


async def _vote_counts_by_user(db: AsyncSession, session_id: uuid.UUID) -> dict[uuid.UUID, int]:
    rows = await db.execute(
        select(Vote.user_id, func.count())
        .where(Vote.session_id == session_id)
        .group_by(Vote.user_id)
    )
    return {uid: int(n) for uid, n in rows.all()}


async def build_out(
    db: AsyncSession, sess: PremortemSession, user: User, member: WorkspaceMember
) -> SessionOut:
    participants = await _participants(db, sess.id)
    facilitator = await db.get(User, sess.facilitator_id)
    creator = await db.get(User, sess.created_by)
    assert facilitator is not None and creator is not None

    risks_total = int(
        await db.scalar(select(func.count()).select_from(Risk).where(Risk.session_id == sess.id))
        or 0
    )
    canonical = await canonical_count(db, sess.id)
    vote_counts = await _vote_counts_by_user(db, sess.id)
    voters_complete = (
        sum(1 for p in participants if vote_counts.get(p.id, 0) >= canonical) if canonical else 0
    )
    my_risks = int(
        await db.scalar(
            select(func.count())
            .select_from(Risk)
            .where(Risk.session_id == sess.id, Risk.author_id == user.id)
        )
        or 0
    )
    participant_ids = {p.id for p in participants}
    votes_required = canonical if sess.phase in (SessionPhase.vote, SessionPhase.sealed) else 0

    return SessionOut(
        id=sess.id,
        project_id=sess.project_id,
        workspace_id=sess.workspace_id,
        phase=sess.phase,
        facilitator=UserRef.model_validate(facilitator, from_attributes=True),
        created_by=UserRef.model_validate(creator, from_attributes=True),
        phase_changed_at=sess.phase_changed_at,
        sealed_at=sess.sealed_at,
        fully_graded_at=sess.fully_graded_at,
        participants=[UserRef.model_validate(p, from_attributes=True) for p in participants],
        counts=SessionCounts(
            risks_total=risks_total,
            risks_canonical=canonical,
            participants=len(participants),
            voters_complete=voters_complete,
        ),
        me=SessionMe(
            is_facilitator=is_facilitator(sess, member, user),
            is_participant=user.id in participant_ids,
            risks_submitted=my_risks,
            votes_cast=vote_counts.get(user.id, 0),
            votes_required=votes_required,
        ),
    )


async def _require_workspace_members(
    db: AsyncSession, workspace_id: uuid.UUID, user_ids: list[uuid.UUID]
) -> None:
    if not user_ids:
        return
    rows = await db.execute(
        select(WorkspaceMember.user_id).where(
            WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id.in_(user_ids)
        )
    )
    found = {row[0] for row in rows.all()}
    missing = [str(u) for u in user_ids if u not in found]
    if missing:
        raise AppError(
            400,
            "not_a_member",
            "Every participant must be a member of the workspace",
            {"user_ids": missing},
        )


async def create(
    db: AsyncSession,
    project: Project,
    member: WorkspaceMember,
    user: User,
    participant_ids: list[uuid.UUID],
) -> SessionOut:
    if project.status == ProjectStatus.closed:
        raise AppError(409, "project_closed", "Closed projects cannot start a pre-mortem")
    if project.archived_at is not None:
        raise AppError(409, "project_archived", "Archived projects cannot start a pre-mortem")
    existing = await db.scalar(
        select(PremortemSession.id).where(PremortemSession.project_id == project.id)
    )
    if existing is not None:
        raise AppError(409, "session_exists", "This project already has a pre-mortem session")
    ids = list(dict.fromkeys([user.id, *participant_ids]))
    await _require_workspace_members(db, project.workspace_id, ids)
    sess = PremortemSession(
        project_id=project.id,
        workspace_id=project.workspace_id,
        created_by=user.id,
        facilitator_id=user.id,
    )
    db.add(sess)
    await db.flush()
    for uid in ids:
        db.add(SessionParticipant(session_id=sess.id, user_id=uid, added_by=user.id))
    await db.commit()
    return await build_out(db, sess, user, member)


async def set_facilitator(
    db: AsyncSession,
    sess: PremortemSession,
    member: WorkspaceMember,
    user: User,
    new_facilitator_id: uuid.UUID,
) -> SessionOut:
    await _require_workspace_members(db, sess.workspace_id, [new_facilitator_id])
    sess.facilitator_id = new_facilitator_id
    if await db.get(SessionParticipant, (sess.id, new_facilitator_id)) is None:
        db.add(SessionParticipant(session_id=sess.id, user_id=new_facilitator_id, added_by=user.id))
    await db.commit()
    return await build_out(db, sess, user, member)


async def add_participants(
    db: AsyncSession, sess: PremortemSession, user: User, user_ids: list[uuid.UUID]
) -> None:
    if sess.phase == SessionPhase.sealed:
        raise AppError(409, "session_sealed", "The session is sealed")
    ids = list(dict.fromkeys(user_ids))
    await _require_workspace_members(db, sess.workspace_id, ids)
    for uid in ids:
        if await db.get(SessionParticipant, (sess.id, uid)) is None:
            db.add(SessionParticipant(session_id=sess.id, user_id=uid, added_by=user.id))
    await db.commit()


async def remove_participant(db: AsyncSession, sess: PremortemSession, user_id: uuid.UUID) -> None:
    if sess.phase == SessionPhase.sealed:
        raise AppError(409, "session_sealed", "The session is sealed")
    if user_id == sess.facilitator_id:
        raise AppError(409, "cannot_remove_facilitator", "Reassign the facilitator first")
    row = await db.get(SessionParticipant, (sess.id, user_id))
    if row is None:
        raise not_found("Participant")
    has_votes = await db.scalar(
        select(Vote.id).where(Vote.session_id == sess.id, Vote.user_id == user_id).limit(1)
    )
    if has_votes is not None:
        raise AppError(409, "participant_has_votes", "This participant has already voted")
    await db.delete(row)
    await db.commit()


async def transition(
    db: AsyncSession,
    sess: PremortemSession,
    member: WorkspaceMember,
    user: User,
    to: str,
) -> SessionTransitionResult:
    require_facilitator(sess, member, user)
    target = SessionPhase(to)
    expected = NEXT_PHASE.get(sess.phase)
    if expected is None or target != expected:
        raise AppError(409, "invalid_transition", f"Cannot move from {sess.phase} to {target}")
    incomplete: list[UserRef] = []
    if target == SessionPhase.merge:
        total = await db.scalar(
            select(func.count()).select_from(Risk).where(Risk.session_id == sess.id)
        )
        if not total:
            raise AppError(409, "no_risks", "Collect at least one risk before merging")
    elif target == SessionPhase.vote:
        if await canonical_count(db, sess.id) == 0:
            raise AppError(409, "no_risks", "At least one canonical risk is required")
    elif target == SessionPhase.sealed:
        incomplete = await votes_service.seal(db, sess)

    values: dict[str, object] = {"phase": target, "phase_changed_at": _now()}
    if target == SessionPhase.sealed:
        values["sealed_at"] = _now()
    result = await db.execute(
        update(PremortemSession)
        .where(PremortemSession.id == sess.id, PremortemSession.phase == sess.phase)
        .values(**values)
    )
    if int(getattr(result, "rowcount", 0)) != 1:
        await db.rollback()
        raise AppError(409, "invalid_transition", "The session changed phase concurrently")
    await db.commit()
    await db.refresh(sess)
    return SessionTransitionResult(
        session=await build_out(db, sess, user, member), incomplete_voters=incomplete
    )


async def delete(db: AsyncSession, sess: PremortemSession) -> None:
    if sess.phase not in (SessionPhase.collect, SessionPhase.merge):
        raise AppError(409, "phase_locked", "Sessions can only be deleted before voting starts")
    await db.execute(sa_delete(PremortemSession).where(PremortemSession.id == sess.id))
    await db.commit()
