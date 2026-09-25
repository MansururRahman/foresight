from typing import Annotated

from fastapi import APIRouter, Cookie, Header, Response, status

from app.core.config import Settings
from app.core.errors import AppError
from app.deps import CurrentUser, KeyPairDep, SessionDep, SettingsDep
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut
from app.services import tokens, users

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "fs_refresh"
COOKIE_PATH = "/auth"


def _set_refresh_cookie(response: Response, value: str, settings: Settings) -> None:
    response.set_cookie(
        COOKIE_NAME,
        value,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=COOKIE_PATH,
        max_age=settings.refresh_ttl_days * 86400,
    )


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenOut)
async def register(
    body: RegisterIn,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    kp: KeyPairDep,
    user_agent: Annotated[str | None, Header()] = None,
) -> TokenOut:
    user = await users.register(session, body.email, body.name, body.password)
    access, refresh = await tokens.issue_pair(session, user, kp, settings, user_agent)
    _set_refresh_cookie(response, refresh, settings)
    return TokenOut(
        access_token=access,
        expires_in=settings.access_ttl_seconds,
        user=UserOut.model_validate(user, from_attributes=True),
    )


@router.post("/login", response_model=TokenOut)
async def login(
    body: LoginIn,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    kp: KeyPairDep,
    user_agent: Annotated[str | None, Header()] = None,
) -> TokenOut:
    user = await users.authenticate(session, body.email, body.password)
    access, refresh = await tokens.issue_pair(session, user, kp, settings, user_agent)
    _set_refresh_cookie(response, refresh, settings)
    return TokenOut(
        access_token=access,
        expires_in=settings.access_ttl_seconds,
        user=UserOut.model_validate(user, from_attributes=True),
    )


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    kp: KeyPairDep,
    fs_refresh: Annotated[str | None, Cookie()] = None,
    user_agent: Annotated[str | None, Header()] = None,
) -> TokenOut:
    if not fs_refresh:
        raise AppError(401, "invalid_refresh", "No refresh token")
    access, new_refresh, user = await tokens.rotate(session, fs_refresh, kp, settings, user_agent)
    _set_refresh_cookie(response, new_refresh, settings)
    return TokenOut(
        access_token=access,
        expires_in=settings.access_ttl_seconds,
        user=UserOut.model_validate(user, from_attributes=True),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: SessionDep,
    fs_refresh: Annotated[str | None, Cookie()] = None,
) -> Response:
    if fs_refresh:
        await tokens.revoke_family_by_token(session, fs_refresh)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH)
    return response


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user, from_attributes=True)
