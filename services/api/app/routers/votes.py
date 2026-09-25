import uuid

from fastapi import APIRouter

from app.core.errors import AppError
from app.deps import CurrentUser, SessionDep
from app.schemas.vote import MyVotes, ResultsOut, VotesPut
from app.services import sessions, votes

router = APIRouter(prefix="/v1", tags=["votes"])


async def _require_participant(session, sess, user) -> None:  # type: ignore[no-untyped-def]
    if not await sessions.is_participant(session, sess, user):
        raise AppError(403, "not_participant", "Only participants can vote in this session")


@router.get("/sessions/{session_id}/votes/me", response_model=MyVotes)
async def get_my_votes(session_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> MyVotes:
    sess, _, _ = await sessions.load_for_member(session, session_id, user)
    await _require_participant(session, sess, user)
    return await votes.my_votes(session, sess, user)


@router.put("/sessions/{session_id}/votes", response_model=MyVotes)
async def put_my_votes(
    session_id: uuid.UUID, body: VotesPut, user: CurrentUser, session: SessionDep
) -> MyVotes:
    sess, _, _ = await sessions.load_for_member(session, session_id, user)
    await _require_participant(session, sess, user)
    return await votes.put_votes(session, sess, user, body.votes)


@router.get("/sessions/{session_id}/results", response_model=ResultsOut)
async def get_results(session_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> ResultsOut:
    sess, _, member = await sessions.load_for_member(session, session_id, user)
    return await votes.results(session, sess, user, member)
