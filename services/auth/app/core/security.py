"""Password hashing, access-token signing, refresh-token generation/hashing."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import Settings
from app.core.keys import KeyPair
from app.models.user import User

_hasher = PasswordHasher()

# Used to keep login timing constant when the email is unknown.
DUMMY_HASH = _hasher.hash("dummy-password-for-constant-time")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def sign_access_token(kp: KeyPair, user: User, settings: Settings) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.access_ttl_seconds)).timestamp()),
        "jti": uuid.uuid4().hex,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(claims, kp.private_key, algorithm="RS256", headers={"kid": kp.kid})


def decode_access_token(token: str, kp: KeyPair, settings: Settings) -> dict[str, object]:
    return jwt.decode(
        token,
        kp.public_key,
        algorithms=["RS256"],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        leeway=10,
        options={"require": ["exp", "iat", "sub"]},
    )


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
