import uuid

from fastapi import APIRouter, Response, status

from app.deps import CurrentUser, SessionDep
from app.schemas.grading import CloseoutOut, GradingsPut, ProjectReport, SurpriseCreate
from app.schemas.risk import RiskOut
from app.services import grading, projects

router = APIRouter(prefix="/v1", tags=["closeout"])


@router.get("/projects/{project_id}/closeout", response_model=CloseoutOut)
async def get_closeout(
    project_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> CloseoutOut:
    project, member = await projects.load_for_member(session, project_id, user)
    return await grading.closeout(session, project, member, user)


@router.put("/projects/{project_id}/gradings", response_model=CloseoutOut)
async def put_gradings(
    project_id: uuid.UUID, body: GradingsPut, user: CurrentUser, session: SessionDep
) -> CloseoutOut:
    project, member = await projects.load_for_member(session, project_id, user)
    return await grading.put_gradings(session, project, member, user, body.gradings)


@router.delete("/gradings/{risk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_grading(risk_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> Response:
    from app.services import risks as risks_service

    risk, _, project, member = await risks_service.load_for_member(session, risk_id, user)
    await grading.delete_grading(session, project, member, user, risk.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/projects/{project_id}/surprises", status_code=status.HTTP_201_CREATED, response_model=RiskOut
)
async def add_surprise(
    project_id: uuid.UUID, body: SurpriseCreate, user: CurrentUser, session: SessionDep
) -> RiskOut:
    project, member = await projects.load_for_member(session, project_id, user)
    return await grading.add_surprise(session, project, member, user, body)


@router.get("/projects/{project_id}/report", response_model=ProjectReport)
async def get_report(
    project_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> ProjectReport:
    project, member = await projects.load_for_member(session, project_id, user)
    return await grading.report(session, project, member, user)
