import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.core.errors import AppError
from app.deps import CurrentUser, SessionDep, is_admin, require_membership
from app.models import ProjectStatus, WorkspaceRole
from app.schemas.project import (
    ProjectCreate,
    ProjectOut,
    ProjectPage,
    ProjectPatch,
    ProjectTransition,
    TransitionResult,
)
from app.services import projects

router = APIRouter(prefix="/v1", tags=["projects"])


@router.post(
    "/workspaces/{workspace_id}/projects",
    status_code=status.HTTP_201_CREATED,
    response_model=ProjectOut,
)
async def create_project(
    workspace_id: uuid.UUID, body: ProjectCreate, user: CurrentUser, session: SessionDep
) -> ProjectOut:
    await require_membership(session, workspace_id, user)
    return await projects.create(session, workspace_id, user, body)


@router.get("/workspaces/{workspace_id}/projects", response_model=ProjectPage)
async def list_projects(
    workspace_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    status_filter: Annotated[ProjectStatus | None, Query(alias="status")] = None,
    tag: str | None = None,
    q: str | None = None,
    include_archived: bool = False,
    cursor: str | None = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> ProjectPage:
    await require_membership(session, workspace_id, user)
    return await projects.list_projects(
        session,
        workspace_id,
        status=status_filter,
        tag=tag,
        q=q,
        include_archived=include_archived,
        cursor=cursor,
        limit=limit,
    )


@router.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(project_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> ProjectOut:
    project, _ = await projects.load_for_member(session, project_id, user)
    return await projects.load_out(session, project.id)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
async def patch_project(
    project_id: uuid.UUID, body: ProjectPatch, user: CurrentUser, session: SessionDep
) -> ProjectOut:
    project, member = await projects.load_for_member(session, project_id, user)
    return await projects.patch(session, project, member, user, body)


@router.post("/projects/{project_id}/transition", response_model=TransitionResult)
async def transition_project(
    project_id: uuid.UUID, body: ProjectTransition, user: CurrentUser, session: SessionDep
) -> TransitionResult:
    project, member = await projects.load_for_member(session, project_id, user)
    return await projects.transition(session, project, member, user, body.to)


@router.post("/projects/{project_id}/archive", response_model=ProjectOut)
async def archive_project(
    project_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> ProjectOut:
    project, member = await projects.load_for_member(session, project_id, user)
    if not is_admin(member):
        raise AppError(
            403, "insufficient_role", f"This action requires the {WorkspaceRole.admin} role"
        )
    return await projects.set_archived(session, project, True)


@router.post("/projects/{project_id}/unarchive", response_model=ProjectOut)
async def unarchive_project(
    project_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> ProjectOut:
    project, member = await projects.load_for_member(session, project_id, user)
    if not is_admin(member):
        raise AppError(
            403, "insufficient_role", f"This action requires the {WorkspaceRole.admin} role"
        )
    return await projects.set_archived(session, project, False)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> Response:
    project, member = await projects.load_for_member(session, project_id, user)
    if not is_admin(member):
        raise AppError(
            403, "insufficient_role", f"This action requires the {WorkspaceRole.admin} role"
        )
    await projects.delete(session, project)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
