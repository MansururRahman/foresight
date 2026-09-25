import uuid

from fastapi import APIRouter, Response, status

from app.core.errors import AppError
from app.deps import CurrentUser, SessionDep
from app.models import RiskOrigin
from app.schemas.risk import RiskAdopt, RiskCreate, RiskList, RiskOut, RiskPatch
from app.services import grading, risks, sessions

router = APIRouter(prefix="/v1", tags=["risks"])


@router.get("/sessions/{session_id}/risks", response_model=RiskList)
async def list_risks(session_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> RiskList:
    sess, _, member = await sessions.load_for_member(session, session_id, user)
    return await risks.visible_list(
        session,
        sess,
        user,
        is_fac=sessions.is_facilitator(sess, member, user),
        is_part=await sessions.is_participant(session, sess, user),
    )


@router.post(
    "/sessions/{session_id}/risks", status_code=status.HTTP_201_CREATED, response_model=RiskOut
)
async def create_risk(
    session_id: uuid.UUID, body: RiskCreate, user: CurrentUser, session: SessionDep
) -> RiskOut:
    sess, _, _ = await sessions.load_for_member(session, session_id, user)
    is_part = await sessions.is_participant(session, sess, user)
    return await risks.create(session, sess, user, is_part=is_part, statement=body.statement)


@router.post(
    "/sessions/{session_id}/risks/adopt",
    status_code=status.HTTP_201_CREATED,
    response_model=RiskOut,
)
async def adopt_risk(
    session_id: uuid.UUID, body: RiskAdopt, user: CurrentUser, session: SessionDep
) -> RiskOut:
    sess, _, member = await sessions.load_for_member(session, session_id, user)
    is_fac = sessions.is_facilitator(sess, member, user)
    return await risks.adopt(session, sess, user, is_fac=is_fac, data=body)


@router.patch("/risks/{risk_id}", response_model=RiskOut)
async def patch_risk(
    risk_id: uuid.UUID, body: RiskPatch, user: CurrentUser, session: SessionDep
) -> RiskOut:
    risk, sess, project, member = await risks.load_for_member(session, risk_id, user)
    if risk.origin == RiskOrigin.surprise or sess is None:
        if "duplicate_of" in body.model_fields_set:
            raise AppError(400, "field_locked", "Surprises cannot be marked as duplicates")
        return await grading.patch_surprise(
            session, project, member, user, risk, statement=body.statement, tags=body.tags
        )
    is_fac = sessions.is_facilitator(sess, member, user)
    return await risks.patch(session, sess, risk, user, is_fac=is_fac, data=body)


@router.delete("/risks/{risk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_risk(risk_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> Response:
    risk, sess, project, member = await risks.load_for_member(session, risk_id, user)
    if risk.origin == RiskOrigin.surprise or sess is None:
        await grading.delete_surprise(session, project, member, user, risk)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    is_fac = sessions.is_facilitator(sess, member, user)
    await risks.delete(session, sess, risk, user, is_fac=is_fac)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
