"""Shared fixtures: migrated test database, per-test rollback session, ASGI test client."""

import os
from collections.abc import AsyncIterator

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "AUTH_TEST_DATABASE_URL",
    "postgresql+asyncpg://foresight_auth:auth_dev_pw@localhost:5433/foresight_auth_test",
)
os.environ["AUTH_DATABASE_URL"] = TEST_DATABASE_URL
os.environ["AUTH_ENV"] = "dev"
os.environ["AUTH_JWT_PRIVATE_KEY_FILE"] = ""
os.environ["AUTH_JWT_PRIVATE_KEY_PEM"] = ""


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
    from app.db.session import get_session
    from app.main import app

    async def _override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
