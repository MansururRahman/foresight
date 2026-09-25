from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.deps import get_keypair
from app.routers import auth, health, jwks


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_keypair()  # load or generate the signing key eagerly so misconfiguration fails fast
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Foresight Auth", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(jwks.router)
    app.include_router(auth.router)
    return app


app = create_app()
