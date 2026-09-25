import re
import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import User, Workspace, WorkspaceMember, WorkspaceRole
from app.schemas.common import UserRef
from app.schemas.workspace import MemberOut, TagStat, WorkspaceOut

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return (slug or "workspace")[:50].strip("-")


async def unique_slug(session: AsyncSession, base: str) -> str:
    candidate, n = base, 1
    while await session.scalar(select(Workspace.id).where(Workspace.slug == candidate)):
        n += 1
        candidate = f"{base[: 50 - len(str(n)) - 1]}-{n}"
    return candidate


def to_out(ws: Workspace, role: WorkspaceRole) -> WorkspaceOut:
    return WorkspaceOut(
        id=ws.id, name=ws.name, slug=ws.slug, my_role=role, created_at=ws.created_at
    )


async def create(session: AsyncSession, user: User, name: str, slug: str | None) -> WorkspaceOut:
    base = slugify(slug or name)
    ws = Workspace(name=name.strip(), slug=await unique_slug(session, base), created_by=user.id)
    session.add(ws)
    await session.flush()
    session.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role=WorkspaceRole.owner))
    await session.commit()
    return to_out(ws, WorkspaceRole.owner)


async def list_for_user(session: AsyncSession, user: User) -> list[WorkspaceOut]:
    rows = await session.execute(
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(Workspace.created_at, Workspace.id)
    )
    return [to_out(ws, role) for ws, role in rows.all()]


async def list_members(session: AsyncSession, workspace_id: uuid.UUID) -> list[MemberOut]:
    rows = await session.execute(
        select(User, WorkspaceMember.role, WorkspaceMember.created_at)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at, User.id)
    )
    return [
        MemberOut(user=UserRef.model_validate(u, from_attributes=True), role=role, joined_at=joined)
        for u, role, joined in rows.all()
    ]


async def owner_count(session: AsyncSession, workspace_id: uuid.UUID) -> int:
    n = await session.scalar(
        select(func.count())
        .select_from(WorkspaceMember)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.role == WorkspaceRole.owner,
        )
    )
    return int(n or 0)


async def add_member(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    actor: WorkspaceMember,
    email: str,
    role: WorkspaceRole,
) -> MemberOut:
    if role == WorkspaceRole.owner and actor.role != WorkspaceRole.owner:
        raise AppError(403, "owner_required", "Only an owner can grant the owner role")
    user = await session.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        raise AppError(
            404,
            "user_not_registered",
            "No registered user with this email. Ask them to sign up first, then add them.",
        )
    existing = await session.get(WorkspaceMember, (workspace_id, user.id))
    if existing is not None:
        raise AppError(409, "already_member", "This user is already a member")
    member = WorkspaceMember(workspace_id=workspace_id, user_id=user.id, role=role)
    session.add(member)
    await session.commit()
    return MemberOut(
        user=UserRef.model_validate(user, from_attributes=True),
        role=role,
        joined_at=member.created_at,
    )


async def set_role(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    actor: WorkspaceMember,
    user_id: uuid.UUID,
    role: WorkspaceRole,
) -> MemberOut:
    target = await session.get(WorkspaceMember, (workspace_id, user_id))
    if target is None:
        raise AppError(404, "not_found", "Member not found")
    touches_owner = role == WorkspaceRole.owner or target.role == WorkspaceRole.owner
    if touches_owner and actor.role != WorkspaceRole.owner:
        raise AppError(403, "owner_required", "Only an owner can change owner roles")
    if (
        target.role == WorkspaceRole.owner
        and role != WorkspaceRole.owner
        and await owner_count(session, workspace_id) <= 1
    ):
        raise AppError(409, "last_owner", "A workspace must keep at least one owner")
    target.role = role
    await session.commit()
    user = await session.get(User, user_id)
    assert user is not None
    return MemberOut(
        user=UserRef.model_validate(user, from_attributes=True),
        role=role,
        joined_at=target.created_at,
    )


async def remove_member(
    session: AsyncSession, workspace_id: uuid.UUID, actor: WorkspaceMember, user_id: uuid.UUID
) -> None:
    target = await session.get(WorkspaceMember, (workspace_id, user_id))
    if target is None:
        raise AppError(404, "not_found", "Member not found")
    if target.role == WorkspaceRole.owner and await owner_count(session, workspace_id) <= 1:
        raise AppError(409, "last_owner", "A workspace must keep at least one owner")
    # Unsealed sessions facilitated by the leaver are handed to the actor (or, on self-leave,
    # to the oldest owner) so no session is left without a facilitator.
    successor = actor.user_id
    if actor.user_id == user_id:
        oldest_owner = await session.scalar(
            select(WorkspaceMember.user_id)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == WorkspaceRole.owner,
                WorkspaceMember.user_id != user_id,
            )
            .order_by(WorkspaceMember.created_at)
            .limit(1)
        )
        successor = oldest_owner or actor.user_id
    await session.execute(
        text(
            "UPDATE premortem_sessions SET facilitator_id = :succ "
            "WHERE workspace_id = :ws AND facilitator_id = :leaver AND phase <> 'sealed'"
        ),
        {"succ": successor, "ws": workspace_id, "leaver": user_id},
    )
    await session.delete(target)
    await session.commit()


async def tag_stats(session: AsyncSession, workspace_id: uuid.UUID) -> list[TagStat]:
    rows = await session.execute(
        text(
            """
            WITH p AS (
              SELECT unnest(tags) AS tag, count(*) AS n
              FROM projects WHERE workspace_id = :ws AND archived_at IS NULL GROUP BY 1
            ), r AS (
              SELECT unnest(tags) AS tag, count(*) AS n
              FROM risks WHERE workspace_id = :ws GROUP BY 1
            )
            SELECT COALESCE(p.tag, r.tag) AS tag,
                   COALESCE(p.n, 0)::int AS project_count,
                   COALESCE(r.n, 0)::int AS risk_count
            FROM p FULL OUTER JOIN r ON p.tag = r.tag
            ORDER BY (COALESCE(p.n, 0) + COALESCE(r.n, 0)) DESC, tag
            """
        ),
        {"ws": workspace_id},
    )
    return [TagStat(tag=t, project_count=pc, risk_count=rc) for t, pc, rc in rows.all()]
