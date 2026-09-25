from fastapi import APIRouter
from pydantic import BaseModel

from app.deps import CurrentUser, SessionDep
from app.schemas.common import UserRef
from app.schemas.workspace import WorkspaceOut
from app.services import workspaces

router = APIRouter(prefix="/v1", tags=["me"])


class MeOut(BaseModel):
    user: UserRef
    workspaces: list[WorkspaceOut]


@router.get("/me", response_model=MeOut)
async def me(user: CurrentUser, session: SessionDep) -> MeOut:
    return MeOut(
        user=UserRef.model_validate(user, from_attributes=True),
        workspaces=await workspaces.list_for_user(session, user),
    )
