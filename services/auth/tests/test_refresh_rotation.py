REG = {"email": "a@b.c", "name": "A", "password": "demo1234"}


async def test_refresh_rotates_and_old_cookie_is_rejected(client):
    r = await client.post("/auth/register", json=REG)
    old = r.cookies["fs_refresh"]

    r2 = await client.post("/auth/refresh")
    assert r2.status_code == 200
    assert r2.json()["user"]["email"] == "a@b.c"
    assert r2.cookies["fs_refresh"] != old

    client.cookies.set("fs_refresh", old, path="/auth")
    r3 = await client.post("/auth/refresh")
    assert r3.status_code == 401


async def test_refresh_reuse_revokes_family(client):
    r = await client.post("/auth/register", json=REG)
    old = r.cookies["fs_refresh"]
    r2 = await client.post("/auth/refresh")
    new = r2.cookies["fs_refresh"]

    client.cookies.set("fs_refresh", old, path="/auth")
    reuse = await client.post("/auth/refresh")  # replay of a rotated token
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "refresh_reused"

    client.cookies.set("fs_refresh", new, path="/auth")
    r4 = await client.post("/auth/refresh")  # the legitimate successor is now dead too
    assert r4.status_code == 401


async def test_refresh_without_cookie_401(client):
    r = await client.post("/auth/refresh")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_refresh"


async def test_refresh_garbage_cookie_401(client):
    client.cookies.set("fs_refresh", "not-a-real-token", path="/auth")
    r = await client.post("/auth/refresh")
    assert r.status_code == 401
