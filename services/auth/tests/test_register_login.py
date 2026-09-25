REG = {"email": "Ada@Demo.local", "name": "Ada", "password": "demo1234"}


async def test_register_returns_token_and_cookie(client):
    r = await client.post("/auth/register", json=REG)
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["email"] == "ada@demo.local"
    assert body["user"]["name"] == "Ada"
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    assert body["access_token"].count(".") == 2
    assert "fs_refresh" in r.cookies
    set_cookie = r.headers["set-cookie"]
    assert "HttpOnly" in set_cookie and "Path=/auth" in set_cookie and "SameSite=lax" in set_cookie


async def test_register_duplicate_email_409(client):
    await client.post(
        "/auth/register", json={"email": "a@b.c", "name": "A", "password": "demo1234"}
    )
    r = await client.post(
        "/auth/register", json={"email": "A@B.C", "name": "A", "password": "demo1234"}
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_taken"


async def test_login_returns_token(client):
    await client.post(
        "/auth/register", json={"email": "a@b.c", "name": "A", "password": "demo1234"}
    )
    r = await client.post("/auth/login", json={"email": "A@b.c", "password": "demo1234"})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "a@b.c"
    assert "fs_refresh" in r.cookies


async def test_login_wrong_password_401(client):
    await client.post(
        "/auth/register", json={"email": "a@b.c", "name": "A", "password": "demo1234"}
    )
    r = await client.post("/auth/login", json={"email": "a@b.c", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


async def test_login_unknown_email_401(client):
    r = await client.post("/auth/login", json={"email": "ghost@b.c", "password": "x"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


async def test_password_min_length_422(client):
    r = await client.post(
        "/auth/register", json={"email": "a@b.c", "name": "A", "password": "short"}
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
