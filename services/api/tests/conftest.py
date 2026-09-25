"""Shared fixtures: migrated test DB, per-test rollback session, ASGI client, signed test users."""

import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from tests.jwt_utils import TEST_KID, TEST_PUBLIC_KEY, sign

TEST_DATABASE_URL = os.environ.get(
    "API_TEST_DATABASE_URL",
    "postgresql+asyncpg://foresight_api:api_dev_pw@localhost:5433/foresight_api_test",
)
os.environ["API_DATABASE_URL"] = TEST_DATABASE_URL
os.environ["API_ENV"] = "dev"
os.environ["API_AUTH_JWKS_URL"] = "http://auth.test/.well-known/jwks.json"


@pytest.fixture(scope="session", autouse=True)
def migrated_db() -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    from app.core.security import get_jwks_cache
    from app.db.session import get_session
    from app.main import app

    async def _override() -> AsyncIterator[AsyncSession]:
        yield db_session

    get_jwks_cache().set_static({TEST_KID: TEST_PUBLIC_KEY})
    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _make_user(name: str) -> dict[str, Any]:
    uid = str(uuid.uuid4())
    email = f"{name.lower()}-{uid[:8]}@demo.local"
    token = sign(uid, email, name)
    return {
        "id": uid,
        "email": email,
        "name": name,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
def user_a() -> dict[str, Any]:
    return _make_user("Ada")


@pytest.fixture
def user_b() -> dict[str, Any]:
    return _make_user("Grace")


@pytest.fixture
def user_c() -> dict[str, Any]:
    return _make_user("Linus")
