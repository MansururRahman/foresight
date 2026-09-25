import uuid

from fastapi import APIRouter, Response, status

from app.deps import CurrentUser, SessionDep, not_found, require_membership
from app.models import Workspace, WorkspaceRole
from app.schemas.workspace import (
    MemberAdd,
    MemberList,
    MemberOut,
    MemberRoleSet,
    TagList,
    WorkspaceCreate,
    WorkspaceList,
    WorkspaceOut,
    WorkspacePatch,
)
from app.services import workspaces

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=WorkspaceOut)
async def create_workspace(body: WorkspaceCreate, user: CurrentUser, session: SessionDep):
    return await workspaces.create(session, user, body.name, body.slug)


@router.get("", response_model=WorkspaceList)
async def list_workspaces(user: CurrentUser, session: SessionDep):
    return WorkspaceList(items=await workspaces.list_for_user(session, user))


@router.get("/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(workspace_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    member = await require_membership(session, workspace_id, user)
    ws = await session.get(Workspace, workspace_id)
    if ws is None:
        raise not_found("Workspace")
    return workspaces.to_out(ws, member.role)


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
async def patch_workspace(
    workspace_id: uuid.UUID, body: WorkspacePatch, user: CurrentUser, session: SessionDep
):
    member = await require_membership(session, workspace_id, user, WorkspaceRole.admin)
    ws = await session.get(Workspace, workspace_id)
    if ws is None:
        raise not_found("Workspace")
    if body.name is not None:
        ws.name = body.name.strip()
    await session.commit()
    return workspaces.to_out(ws, member.role)


@router.get("/{workspace_id}/members", response_model=MemberList)
async def list_members(workspace_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    await require_membership(session, workspace_id, user)
    return MemberList(items=await workspaces.list_members(session, workspace_id))


@router.post(
    "/{workspace_id}/members", status_code=status.HTTP_201_CREATED, response_model=MemberOut
)
async def add_member(
    workspace_id: uuid.UUID, body: MemberAdd, user: CurrentUser, session: SessionDep
):
    actor = await require_membership(session, workspace_id, user, WorkspaceRole.admin)
    return await workspaces.add_member(session, workspace_id, actor, body.email, body.role)


@router.put("/{workspace_id}/members/{user_id}", response_model=MemberOut)
async def set_member_role(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    body: MemberRoleSet,
    user: CurrentUser,
    session: SessionDep,
):
    actor = await require_membership(session, workspace_id, user, WorkspaceRole.admin)
    return await workspaces.set_role(session, workspace_id, actor, user_id, body.role)


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    workspace_id: uuid.UUID, user_id: uuid.UUID, user: CurrentUser, session: SessionDep
):
    min_role = WorkspaceRole.member if user_id == user.id else WorkspaceRole.admin
    actor = await require_membership(session, workspace_id, user, min_role)
    await workspaces.remove_member(session, workspace_id, actor, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{workspace_id}/tags", response_model=TagList)
async def list_tags(workspace_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    await require_membership(session, workspace_id, user)
    return TagList(items=await workspaces.tag_stats(session, workspace_id))
