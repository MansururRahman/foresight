from fastapi import APIRouter
from pydantic import BaseModel

from app.deps import CurrentUser, SessionDep
from app.schemas.common import UserRef

router = APIRouter(prefix="/v1", tags=["me"])


class MeOut(BaseModel):
    user: UserRef
    workspaces: list[dict[str, object]]


@router.get("/me", response_model=MeOut)
async def me(user: CurrentUser, session: SessionDep) -> MeOut:
    return MeOut(user=UserRef.model_validate(user, from_attributes=True), workspaces=[])
