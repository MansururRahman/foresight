"""Access-token verification against the auth service's JWKS, with an in-process cache."""

import asyncio
import time
from functools import lru_cache
from typing import TypedDict

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from app.core.config import get_settings
from app.core.errors import AppError


class Claims(TypedDict):
    sub: str
    email: str
    name: str


class JWKSCache:
    """Caches public keys by kid. Refetches when stale or when an unknown kid appears,
    but never more often than `min_refetch` seconds for unknown kids."""

    def __init__(self, url: str, ttl: int, min_refetch: int) -> None:
        self._url = url
        self._ttl = ttl
        self._min = min_refetch
        self._keys: dict[str, RSAPublicKey] = {}
        self._fetched_at = 0.0
        self._lock = asyncio.Lock()
        self._static = False

    def set_static(self, keys: dict[str, RSAPublicKey]) -> None:
        """Test hook: serve these keys and never touch the network."""
        self._keys = dict(keys)
        self._static = True
        self._fetched_at = time.monotonic()

    async def _fetch(self) -> None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(self._url)
            response.raise_for_status()
            data = response.json()
        keys: dict[str, RSAPublicKey] = {}
        for jwk in data.get("keys", []):
            key = jwt.PyJWK(jwk).key
            if isinstance(key, RSAPublicKey) and "kid" in jwk:
                keys[str(jwk["kid"])] = key
        self._keys = keys
        self._fetched_at = time.monotonic()

    async def get_key(self, kid: str) -> RSAPublicKey | None:
        if self._static:
            return self._keys.get(kid)
        async with self._lock:
            age = time.monotonic() - self._fetched_at
            never_fetched = not self._keys and self._fetched_at == 0.0
            stale = age > self._ttl
            unknown = kid not in self._keys and age > self._min
            if never_fetched or stale or unknown:
                try:
                    await self._fetch()
                except (httpx.HTTPError, ValueError, jwt.PyJWTError):
                    pass
            return self._keys.get(kid)


@lru_cache
def get_jwks_cache() -> JWKSCache:
    s = get_settings()
    return JWKSCache(s.auth_jwks_url, s.jwks_ttl_seconds, s.jwks_min_refetch_seconds)


async def verify_access_token(token: str) -> Claims:
    settings = get_settings()
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise AppError(401, "invalid_token", "Access token is malformed") from exc
    kid = header.get("kid")
    key = await get_jwks_cache().get_key(str(kid)) if kid else None
    if key is None:
        raise AppError(401, "invalid_token", "Unknown signing key")
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            leeway=10,
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise AppError(401, "invalid_token", "Access token is invalid or expired") from exc
    return Claims(
        sub=str(claims["sub"]),
        email=str(claims.get("email", "")),
        name=str(claims.get("name", "")),
    )
