import uuid

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.deps import CurrentUser, SessionDep, is_admin, not_found, require_membership
from app.models import User, WorkspaceMember
from app.schemas.calibration import UserCalibration, WorkspaceCalibration, WorstCall
from app.schemas.common import UserRef
from app.services import calibration as cal
from app.services import calibration_queries as q

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/calibration", tags=["calibration"])


async def _user_calibration(
    db: AsyncSession, workspace_id: uuid.UUID, target: User
) -> UserCalibration:
    preds = await q.load_predictions(db, workspace_id, target.id)
    base_rate = await q.workspace_base_rate(db, workspace_id)
    s = cal.summary(preds, base_rate)
    worst = [
        WorstCall(
            risk_id=x.risk_id,
            project_id=x.project_id,
            project_title=x.project_title,
            statement=x.statement,
            probability=x.probability,
            outcome=q.outcome_of(x.o),
            brier_contribution=(x.p - x.o) ** 2,
        )
        for x in cal.worst_calls(preds)
    ]
    return UserCalibration(
        **s.model_dump(),
        user=UserRef.model_validate(target, from_attributes=True),
        workspace_id=workspace_id,
        worst_calls=worst,
    )


@router.get("/me", response_model=UserCalibration)
async def my_calibration(
    workspace_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> UserCalibration:
    await require_membership(session, workspace_id, user)
    return await _user_calibration(session, workspace_id, user)


@router.get("/users/{user_id}", response_model=UserCalibration)
async def user_calibration(
    workspace_id: uuid.UUID, user_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> UserCalibration:
    member = await require_membership(session, workspace_id, user)
    if user_id != user.id and not is_admin(member):
        raise AppError(403, "insufficient_role", "Only admins can view other members' calibration")
    target = await session.get(User, user_id)
    target_member = await session.get(WorkspaceMember, (workspace_id, user_id))
    if target is None or target_member is None:
        raise not_found("Member")
    return await _user_calibration(session, workspace_id, target)


@router.get("", response_model=WorkspaceCalibration)
async def workspace_calibration(
    workspace_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> WorkspaceCalibration:
    member = await require_membership(session, workspace_id, user)
    preds = await q.load_predictions(session, workspace_id)
    base_rate = await q.workspace_base_rate(session, workspace_id)
    s = cal.summary(preds, base_rate)
    return WorkspaceCalibration(
        **s.model_dump(exclude={"sample"}),
        workspace_id=workspace_id,
        sample=await q.workspace_sample(session, workspace_id, preds),
        blind_spots=await q.blind_spots(session, workspace_id),
        false_alarms=await q.false_alarms(session, workspace_id),
        tags=await q.tag_stats(session, workspace_id),
        surprises=await q.surprise_stats(session, workspace_id),
        members=await q.member_stats(session, workspace_id) if is_admin(member) else None,
    )
