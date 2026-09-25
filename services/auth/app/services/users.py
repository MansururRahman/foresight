from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import DUMMY_HASH, hash_password, verify_password
from app.models.user import User


async def register(session: AsyncSession, email: str, name: str, password: str) -> User:
    user = User(
        email=email.strip().lower(), name=name.strip(), password_hash=hash_password(password)
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "email_taken", "An account with this email already exists") from exc
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await session.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        verify_password(DUMMY_HASH, password)  # constant-time: always run a verification
        raise AppError(401, "invalid_credentials", "Email or password is incorrect")
    if not verify_password(user.password_hash, password) or not user.is_active:
        raise AppError(401, "invalid_credentials", "Email or password is incorrect")
    return user
