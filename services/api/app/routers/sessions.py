import uuid

from fastapi import APIRouter, Response, status

from app.core.errors import AppError
from app.deps import CurrentUser, SessionDep, is_admin
from app.schemas.session import (
    ParticipantsAdd,
    SessionCreate,
    SessionOut,
    SessionPatch,
    SessionTransition,
    SessionTransitionResult,
)
from app.services import projects, sessions

router = APIRouter(prefix="/v1", tags=["sessions"])


@router.post(
    "/projects/{project_id}/session",
    status_code=status.HTTP_201_CREATED,
    response_model=SessionOut,
)
async def create_session(
    project_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    body: SessionCreate | None = None,
) -> SessionOut:
    project, member = await projects.load_for_member(session, project_id, user)
    ids = body.participant_ids if body else []
    return await sessions.create(session, project, member, user, ids)


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session(session_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> SessionOut:
    sess, _, member = await sessions.load_for_member(session, session_id, user)
    return await sessions.build_out(session, sess, user, member)


@router.patch("/sessions/{session_id}", response_model=SessionOut)
async def patch_session(
    session_id: uuid.UUID, body: SessionPatch, user: CurrentUser, session: SessionDep
) -> SessionOut:
    sess, _, member = await sessions.load_for_member(session, session_id, user)
    if not is_admin(member):
        raise AppError(403, "insufficient_role", "Only an admin can reassign the facilitator")
    return await sessions.set_facilitator(session, sess, member, user, body.facilitator_id)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> Response:
    sess, _, member = await sessions.load_for_member(session, session_id, user)
    sessions.require_facilitator(sess, member, user)
    await sessions.delete(session, sess)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions/{session_id}/transition", response_model=SessionTransitionResult)
async def transition_session(
    session_id: uuid.UUID, body: SessionTransition, user: CurrentUser, session: SessionDep
) -> SessionTransitionResult:
    sess, _, member = await sessions.load_for_member(session, session_id, user)
    return await sessions.transition(session, sess, member, user, body.to)


@router.post("/sessions/{session_id}/participants", response_model=SessionOut)
async def add_participants(
    session_id: uuid.UUID, body: ParticipantsAdd, user: CurrentUser, session: SessionDep
) -> SessionOut:
    sess, _, member = await sessions.load_for_member(session, session_id, user)
    sessions.require_facilitator(sess, member, user)
    await sessions.add_participants(session, sess, user, body.user_ids)
    return await sessions.build_out(session, sess, user, member)


@router.delete(
    "/sessions/{session_id}/participants/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_participant(
    session_id: uuid.UUID, user_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Response:
    sess, _, member = await sessions.load_for_member(session, session_id, user)
    sessions.require_facilitator(sess, member, user)
    await sessions.remove_participant(session, sess, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
