from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.security import get_jwks_cache
from app.routers import health, me, projects, risks, sessions, workspaces


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Warm the JWKS cache; failures are tolerated (auth may still be starting).
    await get_jwks_cache().get_key("warmup")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Foresight API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(workspaces.router)
    app.include_router(projects.router)
    app.include_router(sessions.router)
    app.include_router(risks.router)
    return app


app = create_app()
