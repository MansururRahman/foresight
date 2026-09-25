import time
import uuid

import respx
from httpx import Response

from tests.jwt_utils import TEST_KID, public_jwk, sign


async def test_me_requires_token(client):
    r = await client.get("/v1/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "missing_token"


async def test_me_mirrors_user(client, user_a, db_session):
    from app.models.user import User

    r = await client.get("/v1/me", headers=user_a["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == user_a["email"]
    assert body["user"]["id"] == user_a["id"]
    assert body["workspaces"] == []
    row = await db_session.get(User, uuid.UUID(user_a["id"]))
    assert row is not None and row.name == user_a["name"]


async def test_me_updates_changed_name(client, user_a):
    await client.get("/v1/me", headers=user_a["headers"])
    tok = sign(user_a["id"], user_a["email"], "Renamed")
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["user"]["name"] == "Renamed"


async def test_wrong_audience_401(client, user_a):
    tok = sign(user_a["id"], user_a["email"], user_a["name"], aud="other")
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


async def test_wrong_issuer_401(client, user_a):
    tok = sign(user_a["id"], user_a["email"], user_a["name"], iss="someone-else")
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401


async def test_expired_401(client, user_a):
    tok = sign(user_a["id"], user_a["email"], user_a["name"], exp=int(time.time()) - 100)
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401


async def test_unknown_kid_401(client, user_a):
    tok = sign(user_a["id"], user_a["email"], user_a["name"], kid="nope")
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


@respx.mock
async def test_unknown_kid_triggers_refetch():
    from app.core.security import JWKSCache

    url = "http://auth.test/.well-known/jwks.json"
    route = respx.get(url).mock(return_value=Response(200, json={"keys": [public_jwk()]}))
    cache = JWKSCache(url=url, ttl=600, min_refetch=30)

    key = await cache.get_key(TEST_KID)
    assert key is not None
    assert route.call_count == 1

    # Known kid within TTL: served from cache.
    assert await cache.get_key(TEST_KID) is not None
    assert route.call_count == 1

    # Unknown kid inside the min-refetch window: no refetch, no key.
    assert await cache.get_key("other") is None
    assert route.call_count == 1

    # Unknown kid once the window has passed: exactly one refetch.
    cache._fetched_at -= 31
    assert await cache.get_key("other") is None
    assert route.call_count == 2
