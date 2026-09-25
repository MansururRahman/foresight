import jwt

REG = {"email": "a@b.c", "name": "A", "password": "demo1234"}


async def test_jwks_verifies_issued_token(client):
    r = await client.post("/auth/register", json=REG)
    tok = r.json()["access_token"]

    jr = await client.get("/.well-known/jwks.json")
    assert jr.status_code == 200
    assert jr.headers["cache-control"] == "public, max-age=300"
    jwks = jr.json()
    assert len(jwks["keys"]) == 1

    key = jwt.PyJWK(jwks["keys"][0]).key
    claims = jwt.decode(
        tok, key, algorithms=["RS256"], audience="foresight-api", issuer="foresight-auth"
    )
    assert claims["email"] == "a@b.c"
    assert claims["name"] == "A"
    assert claims["sub"] == r.json()["user"]["id"]
    assert "jti" in claims and "iat" in claims and "exp" in claims
    assert claims["exp"] - claims["iat"] == 900
    assert jwt.get_unverified_header(tok)["kid"] == jwks["keys"][0]["kid"]
