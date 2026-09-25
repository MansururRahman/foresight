import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.pagination import clamp_limit, decode_cursor, encode_cursor
from app.deps import is_admin, not_found
from app.models import (
    Grading,
    PremortemSession,
    Project,
    ProjectStatus,
    Risk,
    SessionPhase,
    User,
    WorkspaceMember,
)
from app.schemas.common import UserRef
from app.schemas.project import (
    ProjectCreate,
    ProjectOut,
    ProjectPage,
    ProjectPatch,
    SessionSummary,
    TransitionResult,
    TransitionWarning,
)


def _now() -> datetime:
    return datetime.now(UTC)


def to_out(project: Project, creator: User, sess: PremortemSession | None) -> ProjectOut:
    summary = (
        SessionSummary(
            id=sess.id,
            phase=sess.phase,
            sealed_at=sess.sealed_at,
            fully_graded_at=sess.fully_graded_at,
        )
        if sess is not None
        else None
    )
    return ProjectOut(
        id=project.id,
        workspace_id=project.workspace_id,
        title=project.title,
        description=project.description,
        tags=list(project.tags),
        planned_start=project.planned_start,
        planned_end=project.planned_end,
        status=project.status,
        activated_at=project.activated_at,
        closed_at=project.closed_at,
        archived_at=project.archived_at,
        created_by=UserRef.model_validate(creator, from_attributes=True),
        created_at=project.created_at,
        updated_at=project.updated_at,
        session=summary,
    )


def _base_query() -> Select[Project, User, PremortemSession]:
    return (
        select(Project, User, PremortemSession)
        .join(User, User.id == Project.created_by)
        .outerjoin(PremortemSession, PremortemSession.project_id == Project.id)
    )


async def load_out(session: AsyncSession, project_id: uuid.UUID) -> ProjectOut:
    row = (await session.execute(_base_query().where(Project.id == project_id))).first()
    if row is None:
        raise not_found("Project")
    project, creator, sess = row
    return to_out(project, creator, sess)


async def load_for_member(
    session: AsyncSession, project_id: uuid.UUID, user: User
) -> tuple[Project, WorkspaceMember]:
    """Load a project the caller may see. Non-members get the same 404 as a missing project."""
    project = await session.get(Project, project_id)
    if project is None:
        raise not_found("Project")
    member = await session.get(WorkspaceMember, (project.workspace_id, user.id))
    if member is None:
        raise not_found("Project")
    return project, member


def can_edit(project: Project, member: WorkspaceMember, user: User) -> bool:
    return project.created_by == user.id or is_admin(member)


def require_editor(project: Project, member: WorkspaceMember, user: User) -> None:
    if not can_edit(project, member, user):
        raise AppError(403, "insufficient_role", "Only the project creator or an admin can do this")


async def create(
    session: AsyncSession, workspace_id: uuid.UUID, user: User, data: ProjectCreate
) -> ProjectOut:
    project = Project(
        workspace_id=workspace_id,
        title=data.title,
        description=data.description,
        tags=data.tags,
        planned_start=data.planned_start,
        planned_end=data.planned_end,
        created_by=user.id,
    )
    session.add(project)
    await session.commit()
    return await load_out(session, project.id)


async def list_projects(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    status: ProjectStatus | None,
    tag: str | None,
    q: str | None,
    include_archived: bool,
    cursor: str | None,
    limit: int | None,
) -> ProjectPage:
    size = clamp_limit(limit)
    stmt = _base_query().where(Project.workspace_id == workspace_id)
    if not include_archived:
        stmt = stmt.where(Project.archived_at.is_(None))
    if status is not None:
        stmt = stmt.where(Project.status == status)
    if tag:
        stmt = stmt.where(Project.tags.contains([tag.strip().lower()]))
    if q and q.strip():
        needle = q.strip()
        stmt = stmt.where(
            or_(Project.search_text.op("%")(needle), Project.title.ilike(f"%{needle}%"))
        )
    if cursor:
        ts, ident = decode_cursor(cursor)
        stmt = stmt.where(tuple_(Project.created_at, Project.id) < tuple_(ts, ident))
    stmt = stmt.order_by(Project.created_at.desc(), Project.id.desc()).limit(size + 1)
    rows = (await session.execute(stmt)).all()
    has_more = len(rows) > size
    rows = rows[:size]
    items = [to_out(p, u, s) for p, u, s in rows]
    next_cursor: str | None = None
    if has_more:
        last_project, _, _ = rows[-1]
        next_cursor = encode_cursor(last_project.created_at, last_project.id)
    return ProjectPage(items=items, next_cursor=next_cursor)


async def patch(
    session: AsyncSession, project: Project, member: WorkspaceMember, user: User, data: ProjectPatch
) -> ProjectOut:
    require_editor(project, member, user)
    if project.status == ProjectStatus.closed:
        raise AppError(409, "project_closed", "Closed projects are read-only")
    if data.title is not None:
        project.title = data.title.strip()
    if data.description is not None:
        project.description = data.description
    if data.tags is not None:
        project.tags = data.tags
    if "planned_start" in data.model_fields_set:
        project.planned_start = data.planned_start
    if "planned_end" in data.model_fields_set:
        project.planned_end = data.planned_end
    if (
        project.planned_start is not None
        and project.planned_end is not None
        and project.planned_end < project.planned_start
    ):
        raise AppError(422, "validation_error", "planned_end must not be before planned_start")
    await session.commit()
    return await load_out(session, project.id)


async def _ungraded_count(session: AsyncSession, sess: PremortemSession) -> int:
    n = await session.scalar(
        select(func.count())
        .select_from(Risk)
        .outerjoin(Grading, Grading.risk_id == Risk.id)
        .where(Risk.session_id == sess.id, Risk.duplicate_of.is_(None), Grading.id.is_(None))
    )
    return int(n or 0)


async def transition(
    session: AsyncSession, project: Project, member: WorkspaceMember, user: User, to: str
) -> TransitionResult:
    sess = await session.scalar(
        select(PremortemSession).where(PremortemSession.project_id == project.id)
    )
    warnings: list[TransitionWarning] = []
    if to == "active":
        if project.status != ProjectStatus.planning:
            raise AppError(409, "invalid_transition", f"Cannot activate a {project.status} project")
        require_editor(project, member, user)
        project.status = ProjectStatus.active
        project.activated_at = _now()
    elif to == "closed":
        if project.status != ProjectStatus.active:
            raise AppError(409, "invalid_transition", f"Cannot close a {project.status} project")
        if sess is not None:
            is_fac = sess.facilitator_id == user.id or is_admin(member)
            if not is_fac:
                raise AppError(
                    403, "insufficient_role", "Only the facilitator can close this project"
                )
            if sess.phase != SessionPhase.sealed:
                raise AppError(
                    409, "session_not_sealed", "Seal the pre-mortem session before closing"
                )
            ungraded = await _ungraded_count(session, sess)
            if ungraded:
                warnings.append(TransitionWarning(code="ungraded_risks", count=ungraded))
        else:
            require_editor(project, member, user)
        project.status = ProjectStatus.closed
        project.closed_at = _now()
        project.closed_by = user.id
    else:  # pragma: no cover - schema restricts values
        raise AppError(400, "validation_error", "Unknown transition")
    await session.commit()
    return TransitionResult(project=await load_out(session, project.id), warnings=warnings)


async def set_archived(session: AsyncSession, project: Project, archived: bool) -> ProjectOut:
    project.archived_at = _now() if archived else None
    await session.commit()
    return await load_out(session, project.id)


async def delete(session: AsyncSession, project: Project) -> None:
    sealed = await session.scalar(
        select(PremortemSession.id).where(
            PremortemSession.project_id == project.id,
            PremortemSession.phase == SessionPhase.sealed,
        )
    )
    if sealed is not None:
        raise AppError(
            409,
            "project_has_sealed_session",
            "This project has graded history. Archive it instead of deleting.",
        )
    await session.delete(project)
    await session.commit()
