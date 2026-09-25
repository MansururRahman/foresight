import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import CurrentUser, SessionDep, require_membership
from app.schemas.suggestion import SuggestionQuery, SuggestionsOut
from app.services import projects, suggestions

router = APIRouter(prefix="/v1", tags=["suggestions"])


@router.post("/workspaces/{workspace_id}/suggestions", response_model=SuggestionsOut)
async def suggest_for_draft(
    workspace_id: uuid.UUID, body: SuggestionQuery, user: CurrentUser, session: SessionDep
) -> SuggestionsOut:
    await require_membership(session, workspace_id, user)
    return await suggestions.suggest(
        session,
        workspace_id,
        title=body.title,
        description=body.description,
        tags=body.tags,
        exclude_project_id=body.exclude_project_id,
        limit=body.limit,
    )


@router.get("/projects/{project_id}/suggestions", response_model=SuggestionsOut)
async def suggest_for_project(
    project_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
) -> SuggestionsOut:
    project, _ = await projects.load_for_member(session, project_id, user)
    return await suggestions.suggest(
        session,
        project.workspace_id,
        title=project.title,
        description=project.description,
        tags=list(project.tags),
        exclude_project_id=project.id,
        limit=limit,
    )
