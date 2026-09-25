REG = {"email": "a@b.c", "name": "A", "password": "demo1234"}


async def test_me_with_bearer(client):
    r = await client.post("/auth/register", json=REG)
    tok = r.json()["access_token"]
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.status_code == 200
    assert me.json()["email"] == "a@b.c"
    assert me.json()["id"] == r.json()["user"]["id"]


async def test_me_without_token_401(client):
    r = await client.get("/auth/me")
    assert r.status_code == 401


async def test_me_with_tampered_token_401(client):
    r = await client.post("/auth/register", json=REG)
    tok = r.json()["access_token"]
    head, payload, sig = tok.split(".")
    tampered = f"{head}.{payload}.{sig[:-3]}abc"
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert me.status_code == 401


async def test_logout_clears_cookie_and_revokes(client):
    await client.post("/auth/register", json=REG)
    r = await client.post("/auth/logout")
    assert r.status_code == 204
    assert "fs_refresh" in r.headers.get("set-cookie", "")
    r2 = await client.post("/auth/refresh")
    assert r2.status_code == 401


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
