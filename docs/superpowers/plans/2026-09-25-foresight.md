# Foresight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Foresight, a pre-mortem calibration engine: teams privately predict project risks with probabilities, grade them at close-out, and get calibration dashboards plus history-grounded risk suggestions.

**Architecture:** Three separate services behind Docker Compose: a FastAPI auth service (argon2 passwords, rotating refresh cookies, RS256 access JWTs, JWKS), a FastAPI domain API (verifies JWTs via cached JWKS, owns workspaces/projects/sessions/votes/gradings/calibration/suggestions in its own Postgres database), and a Next.js App Router web app (access token in memory, silent refresh, TanStack Query, Recharts). One Postgres 16 instance hosts two isolated databases.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, asyncpg, Alembic, PyJWT, argon2-cffi, httpx, pytest-asyncio, uv, ruff, mypy; Next.js 15, TypeScript, Tailwind v4, shadcn/ui, TanStack Query, react-hook-form, zod, Recharts, vitest, msw, Playwright; Postgres 16 with pg_trgm and citext.

**Spec:** `docs/superpowers/specs/2026-09-25-foresight-design.md`

## Global Constraints

- Python services pin `requires-python = ">=3.12,<3.13"`; managed by `uv` (`uv python install 3.12`). On this host `uv` is at `C:\Users\YOGA\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe`; add its directory to PATH in each shell.
- Auth and API use SEPARATE Postgres databases and roles: `foresight_auth`/`foresight_api` (+ `_test` twins). The API never reads auth tables.
- Access JWT: RS256, 15 min, claims `sub,email,name,iat,exp,jti,iss="foresight-auth",aud="foresight-api"`, header `kid`. Refresh token: httpOnly cookie `fs_refresh`, `Path=/auth`, `SameSite=Lax`, 30 days, sha256 stored, rotating families.
- API routes are prefixed `/v1`; errors are `{"error": {"code", "message", "details"}}`; cross-workspace access returns 404, never 403.
- Individual votes are never exposed to other users. Risk authorship is exposed only to the facilitator in `merge` and to the author.
- All shell scripts are LF (`.gitattributes` enforces). Postgres data is a named Docker volume, never a bind mount.
- Commits use the message trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Ports: web 3000, api 8000, auth 8001, postgres 5432.

## Review Focus

1. **Refresh-token replay:** presenting an already-rotated refresh cookie must revoke the whole family and return 401, so a stolen old cookie cannot mint tokens (Task 3 test `test_refresh_reuse_revokes_family`).
2. **Cross-workspace object access by id:** `GET /v1/projects/{id}` by a non-member must return 404 with no field leakage (Task 7 test `test_project_get_non_member_404`).
3. **Vote leakage:** `GET /v1/sessions/{id}/results` must never include per-user votes, and `GET /v1/sessions/{id}/risks` in `vote` phase must not include `author` (Task 9 test `test_results_has_no_user_votes`, Task 8 test `test_vote_phase_hides_author`).
4. **Double seal / concurrent transition:** two facilitators sealing at once must produce exactly one seal and one 409 (Task 9 test `test_seal_twice_409`).
5. **Small-sample dashboards:** with fewer than 10 graded predictions the calibration endpoints must return `brier: null` and `sample.sufficient: false` rather than a misleading number (Task 11 test `test_brier_null_under_min_n`).

---

### Task 1: Infrastructure (Postgres, compose, env, keys)

**Files:**
- Create: `docker-compose.yml`, `docker-compose.override.yml`, `.env.example`, `infra/postgres/init/01-create-databases.sh`, `infra/keys/.gitkeep`, `scripts/gen-keys.py`, `package.json` (root)

**Interfaces:**
- Produces: databases `foresight_auth`, `foresight_api`, `foresight_auth_test`, `foresight_api_test`; roles `foresight_auth`, `foresight_api`; env variable names used by every later task (see `.env.example`); `infra/keys/dev_private.pem`.

- [ ] **Step 1: Write `.env.example`**

```
POSTGRES_SUPER_PASSWORD=postgres
AUTH_DB_PASSWORD=auth_dev_pw
API_DB_PASSWORD=api_dev_pw

AUTH_ENV=dev
AUTH_DATABASE_URL=postgresql+asyncpg://foresight_auth:auth_dev_pw@postgres:5432/foresight_auth
AUTH_JWT_PRIVATE_KEY_FILE=/keys/dev_private.pem
AUTH_JWT_PRIVATE_KEY_PEM=
AUTH_JWT_ISSUER=foresight-auth
AUTH_JWT_AUDIENCE=foresight-api
AUTH_ACCESS_TTL_SECONDS=900
AUTH_REFRESH_TTL_DAYS=30
AUTH_COOKIE_SECURE=false
AUTH_WEB_ORIGIN=http://localhost:3000

API_ENV=dev
API_DATABASE_URL=postgresql+asyncpg://foresight_api:api_dev_pw@postgres:5432/foresight_api
API_AUTH_JWKS_URL=http://auth:8001/.well-known/jwks.json
API_JWT_ISSUER=foresight-auth
API_JWT_AUDIENCE=foresight-api
API_WEB_ORIGIN=http://localhost:3000

NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_AUTH_URL=http://localhost:8001
```

- [ ] **Step 2: Write the DB init script** `infra/postgres/init/01-create-databases.sh` (LF endings):

```bash
#!/bin/bash
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
  CREATE ROLE foresight_auth LOGIN PASSWORD '${AUTH_DB_PASSWORD}';
  CREATE ROLE foresight_api  LOGIN PASSWORD '${API_DB_PASSWORD}';
  CREATE DATABASE foresight_auth      OWNER foresight_auth;
  CREATE DATABASE foresight_api       OWNER foresight_api;
  CREATE DATABASE foresight_auth_test OWNER foresight_auth;
  CREATE DATABASE foresight_api_test  OWNER foresight_api;
  REVOKE CONNECT ON DATABASE foresight_auth FROM PUBLIC;
  REVOKE CONNECT ON DATABASE foresight_api  FROM PUBLIC;
  REVOKE CONNECT ON DATABASE foresight_auth_test FROM PUBLIC;
  REVOKE CONNECT ON DATABASE foresight_api_test  FROM PUBLIC;
EOSQL
for db in foresight_auth foresight_auth_test; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" -c "CREATE EXTENSION IF NOT EXISTS citext;"
done
for db in foresight_api foresight_api_test; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" -c "CREATE EXTENSION IF NOT EXISTS citext; CREATE EXTENSION IF NOT EXISTS pg_trgm;"
done
```

Extensions are created by the superuser here because the app roles are not superusers.

- [ ] **Step 3: Write `docker-compose.yml`** with only `postgres` for now (later tasks add services):

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_SUPER_PASSWORD:-postgres}
      AUTH_DB_PASSWORD: ${AUTH_DB_PASSWORD:-auth_dev_pw}
      API_DB_PASSWORD: ${API_DB_PASSWORD:-api_dev_pw}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./infra/postgres/init:/docker-entrypoint-initdb.d:ro
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 20
volumes:
  pgdata: {}
```

- [ ] **Step 4: Write `scripts/gen-keys.py`** (generates a 2048-bit RSA key to `infra/keys/dev_private.pem` if missing, using `cryptography`; run with `uv run --with cryptography python scripts/gen-keys.py`).

- [ ] **Step 5: Write root `package.json`** with scripts `dev:db` (`docker compose up -d postgres`), `dev:auth`, `dev:api`, `dev:web`, `test` (runs all three), `e2e`.

- [ ] **Step 6: Verify** `docker compose up -d postgres`, wait for healthy, then `docker compose exec postgres psql -U postgres -c "\l"` shows the four databases, and `\dx` in `foresight_api` lists `pg_trgm` and `citext`.

- [ ] **Step 7: Commit** `chore: add postgres compose, db init, env example, key generator`

---

### Task 2: Auth service scaffold, config, keys, models, migration

**Files:**
- Create: `services/auth/pyproject.toml`, `services/auth/app/__init__.py`, `services/auth/app/core/config.py`, `services/auth/app/core/keys.py`, `services/auth/app/db/base.py`, `services/auth/app/db/session.py`, `services/auth/app/models/user.py`, `services/auth/app/models/refresh_token.py`, `services/auth/alembic.ini`, `services/auth/alembic/env.py`, `services/auth/alembic/versions/0001_users_refresh_tokens.py`, `services/auth/tests/conftest.py`, `services/auth/tests/test_keys.py`

**Interfaces:**
- Produces: `Settings` (pydantic-settings, prefix `AUTH_`): `env, database_url, jwt_private_key_file, jwt_private_key_pem, jwt_issuer, jwt_audience, access_ttl_seconds, refresh_ttl_days, cookie_secure, web_origin`; `get_settings()` cached.
- `KeyPair` dataclass: `private_key: RSAPrivateKey, public_key: RSAPublicKey, kid: str, private_pem: bytes`; `load_keypair(settings) -> KeyPair`; `jwk_from_public(public_key, kid) -> dict` returning `{"kty":"RSA","use":"sig","alg":"RS256","kid","n","e"}` base64url without padding.
- Models: `User(id: uuid, email: str (citext), name: str, password_hash: str, is_active: bool, created_at, updated_at)`, `RefreshToken(id: uuid, user_id, token_hash: str unique, family_id: uuid, expires_at, revoked_at, replaced_by_id, user_agent, created_at)`.
- `get_session()` async dependency yielding `AsyncSession`.

- [ ] **Step 1: Create the uv project**: `uv init --no-workspace --name foresight-auth services/auth`, set `requires-python`, add deps `fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic pydantic-settings pyjwt[crypto] argon2-cffi httpx` and dev deps `pytest pytest-asyncio ruff mypy`. Add `[tool.pytest.ini_options] asyncio_mode="auto"`, `[tool.ruff] line-length=100`.

- [ ] **Step 2: Write failing test** `tests/test_keys.py`:

```python
from app.core.keys import load_keypair, jwk_from_public
from app.core.config import Settings

def test_generates_key_when_missing(tmp_path):
    s = Settings(database_url="postgresql+asyncpg://x", jwt_private_key_file=str(tmp_path / "k.pem"), env="dev")
    kp = load_keypair(s)
    assert (tmp_path / "k.pem").exists()
    assert len(kp.kid) == 16
    again = load_keypair(s)
    assert again.kid == kp.kid  # stable across loads

def test_jwk_shape():
    s = Settings(database_url="postgresql+asyncpg://x", jwt_private_key_file="", env="dev")
    kp = load_keypair(s)
    jwk = jwk_from_public(kp.public_key, kp.kid)
    assert jwk["kty"] == "RSA" and jwk["alg"] == "RS256" and jwk["kid"] == kp.kid
    assert "=" not in jwk["n"]
```

- [ ] **Step 3: Run** `uv run pytest tests/test_keys.py -v` → FAIL (module missing).

- [ ] **Step 4: Implement** `config.py` and `keys.py`:

```python
# keys.py
import base64, hashlib
from dataclasses import dataclass
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from app.core.config import Settings

@dataclass(frozen=True)
class KeyPair:
    private_key: RSAPrivateKey
    public_key: RSAPublicKey
    kid: str
    private_pem: bytes

def _b64url(n: int) -> str:
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

def _kid(public_key: RSAPublicKey) -> str:
    der = public_key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(der).hexdigest()[:16]

def load_keypair(settings: Settings) -> KeyPair:
    pem: bytes | None = None
    if settings.jwt_private_key_pem:
        pem = settings.jwt_private_key_pem.encode()
    elif settings.jwt_private_key_file and Path(settings.jwt_private_key_file).exists():
        pem = Path(settings.jwt_private_key_file).read_bytes()
    if pem is None:
        if settings.env != "dev":
            raise RuntimeError("No JWT private key configured")
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        if settings.jwt_private_key_file:
            p = Path(settings.jwt_private_key_file); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(pem)
    private_key = serialization.load_pem_private_key(pem, password=None)
    assert isinstance(private_key, RSAPrivateKey)
    public_key = private_key.public_key()
    return KeyPair(private_key, public_key, _kid(public_key), pem)

def jwk_from_public(public_key: RSAPublicKey, kid: str) -> dict[str, str]:
    nums = public_key.public_numbers()
    return {"kty": "RSA", "use": "sig", "alg": "RS256", "kid": kid, "n": _b64url(nums.n), "e": _b64url(nums.e)}
```

- [ ] **Step 5: Run tests** → PASS.

- [ ] **Step 6: Write models, db session, alembic env and migration 0001** (tables per Interfaces; `email` is `CITEXT` via `sqlalchemy.dialects.postgresql.CITEXT`; indexes: `refresh_tokens(user_id)`, `refresh_tokens(family_id)`). `alembic/env.py` uses `async_engine_from_config` and `run_sync`, url from `Settings().database_url`. Test conftest: session-scoped fixture runs `alembic upgrade head` against the test database (`AUTH_DATABASE_URL` env override pointing at `localhost:5432/foresight_auth_test`), function-scoped `db_session` that opens a connection, begins a transaction, yields `AsyncSession(bind=conn, join_transaction_mode="create_savepoint")`, rolls back.

- [ ] **Step 7: Verify** `uv run alembic upgrade head` against the local test DB succeeds and `\dt` shows `users`, `refresh_tokens`.

- [ ] **Step 8: Commit** `feat(auth): scaffold service with config, RSA keys, models and migration`

---

### Task 3: Auth security, token service, routers, tests

**Files:**
- Create: `services/auth/app/core/security.py`, `services/auth/app/core/errors.py`, `services/auth/app/services/users.py`, `services/auth/app/services/tokens.py`, `services/auth/app/schemas/auth.py`, `services/auth/app/routers/auth.py`, `services/auth/app/routers/jwks.py`, `services/auth/app/routers/health.py`, `services/auth/app/deps.py`, `services/auth/app/main.py`, `services/auth/Dockerfile`, `services/auth/tests/test_register_login.py`, `services/auth/tests/test_refresh_rotation.py`, `services/auth/tests/test_logout_me.py`, `services/auth/tests/test_jwks.py`
- Modify: `docker-compose.yml` (add `auth-migrate`, `auth`)

**Interfaces:**
- `security.hash_password(pw) -> str`, `verify_password(hash, pw) -> bool` (argon2id, `PasswordHasher()`), `DUMMY_HASH` constant for constant-time login, `sign_access_token(kp, user, settings) -> str`, `hash_refresh(token) -> str` (sha256 hex), `new_refresh_token() -> str` (32 random bytes urlsafe).
- `tokens.issue_pair(session, user, kp, settings, user_agent) -> tuple[access, refresh]`, `tokens.rotate(session, presented_refresh, kp, settings, user_agent) -> tuple[access, refresh, user]` raising `AppError(401, "invalid_refresh")` and revoking the family on reuse, `tokens.revoke_family_by_token(session, presented_refresh)`.
- HTTP: `POST /auth/register`, `POST /auth/login` → `201/200 {"access_token": str, "token_type": "bearer", "expires_in": 900, "user": {"id","email","name"}}` + `Set-Cookie fs_refresh`; `POST /auth/refresh` → same 200; `POST /auth/logout` → 204 + cookie cleared; `GET /auth/me` → user; `GET /.well-known/jwks.json` → `{"keys":[jwk]}` with `Cache-Control: public, max-age=300`; `GET /health` → `{"status":"ok"}`.
- Error body everywhere: `{"error": {"code": str, "message": str, "details": dict}}`.

- [ ] **Step 1: Write failing tests** (conftest adds `client` fixture: `AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` with `get_session` overridden to the rollback session; settings overridden with `jwt_private_key_file=""` so a fresh key is generated in memory).

```python
# test_register_login.py
async def test_register_returns_token_and_cookie(client):
    r = await client.post("/auth/register", json={"email": "Ada@Demo.local", "name": "Ada", "password": "demo1234"})
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["email"] == "ada@demo.local"
    assert body["token_type"] == "bearer"
    assert "fs_refresh" in r.cookies
    assert "HttpOnly" in r.headers["set-cookie"] and "Path=/auth" in r.headers["set-cookie"]

async def test_register_duplicate_email_409(client):
    await client.post("/auth/register", json={"email": "a@b.c", "name": "A", "password": "demo1234"})
    r = await client.post("/auth/register", json={"email": "A@B.C", "name": "A", "password": "demo1234"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_taken"

async def test_login_wrong_password_401(client):
    await client.post("/auth/register", json={"email": "a@b.c", "name": "A", "password": "demo1234"})
    r = await client.post("/auth/login", json={"email": "a@b.c", "password": "nope"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_credentials"

async def test_login_unknown_email_401(client):
    r = await client.post("/auth/login", json={"email": "ghost@b.c", "password": "x"})
    assert r.status_code == 401

async def test_password_min_length_422(client):
    r = await client.post("/auth/register", json={"email": "a@b.c", "name": "A", "password": "short"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"

# test_refresh_rotation.py
async def test_refresh_rotates_and_old_cookie_is_rejected(client):
    r = await client.post("/auth/register", json={"email": "a@b.c", "name": "A", "password": "demo1234"})
    old = r.cookies["fs_refresh"]
    r2 = await client.post("/auth/refresh")
    assert r2.status_code == 200 and r2.cookies["fs_refresh"] != old
    client.cookies.set("fs_refresh", old, path="/auth")
    r3 = await client.post("/auth/refresh")
    assert r3.status_code == 401

async def test_refresh_reuse_revokes_family(client):
    r = await client.post("/auth/register", json={"email": "a@b.c", "name": "A", "password": "demo1234"})
    old = r.cookies["fs_refresh"]
    r2 = await client.post("/auth/refresh"); new = r2.cookies["fs_refresh"]
    client.cookies.set("fs_refresh", old, path="/auth"); await client.post("/auth/refresh")  # reuse -> family revoked
    client.cookies.set("fs_refresh", new, path="/auth")
    r4 = await client.post("/auth/refresh")
    assert r4.status_code == 401

async def test_refresh_without_cookie_401(client):
    r = await client.post("/auth/refresh"); assert r.status_code == 401

# test_logout_me.py
async def test_me_with_bearer(client):
    r = await client.post("/auth/register", json={"email": "a@b.c", "name": "A", "password": "demo1234"})
    tok = r.json()["access_token"]
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.status_code == 200 and me.json()["email"] == "a@b.c"

async def test_logout_clears_cookie_and_revokes(client):
    await client.post("/auth/register", json={"email": "a@b.c", "name": "A", "password": "demo1234"})
    r = await client.post("/auth/logout"); assert r.status_code == 204
    r2 = await client.post("/auth/refresh"); assert r2.status_code == 401

# test_jwks.py
async def test_jwks_verifies_issued_token(client):
    import jwt
    r = await client.post("/auth/register", json={"email": "a@b.c", "name": "A", "password": "demo1234"})
    tok = r.json()["access_token"]
    jwks = (await client.get("/.well-known/jwks.json")).json()
    key = jwt.PyJWK(jwks["keys"][0]).key
    claims = jwt.decode(tok, key, algorithms=["RS256"], audience="foresight-api", issuer="foresight-auth")
    assert claims["email"] == "a@b.c" and jwt.get_unverified_header(tok)["kid"] == jwks["keys"][0]["kid"]
```

- [ ] **Step 2: Run** → FAIL (app missing).

- [ ] **Step 3: Implement** security, users, tokens, routers, main.

Key parts of `tokens.py`:

```python
async def rotate(session, presented: str, kp, settings, user_agent: str | None):
    row = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh(presented)))
    if row is None:
        raise AppError(401, "invalid_refresh", "Refresh token not recognised")
    now = datetime.now(timezone.utc)
    if row.revoked_at is not None or row.replaced_by_id is not None:
        await session.execute(update(RefreshToken).where(RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=now))
        await session.commit()
        raise AppError(401, "refresh_reused", "Refresh token reuse detected; session revoked")
    if row.expires_at <= now:
        raise AppError(401, "refresh_expired", "Refresh token expired")
    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise AppError(401, "invalid_refresh", "User unavailable")
    new_plain = new_refresh_token()
    new_row = RefreshToken(user_id=user.id, token_hash=hash_refresh(new_plain), family_id=row.family_id,
                           expires_at=now + timedelta(days=settings.refresh_ttl_days), user_agent=user_agent)
    session.add(new_row); await session.flush()
    row.replaced_by_id = new_row.id
    await session.commit()
    return sign_access_token(kp, user, settings), new_plain, user
```

Cookie helper in the router: `response.set_cookie("fs_refresh", value, httponly=True, secure=settings.cookie_secure, samesite="lax", path="/auth", max_age=settings.refresh_ttl_days*86400)`; logout uses `delete_cookie("fs_refresh", path="/auth")`. Login: if user missing, run `verify_password(DUMMY_HASH, password)` anyway, then raise 401. CORS: `allow_origins=[settings.web_origin], allow_credentials=True, allow_methods=["GET","POST","OPTIONS"], allow_headers=["Authorization","Content-Type"]`. Register `AppError` handler and a 422 handler that wraps validation errors into the standard error envelope with `code="validation_error"`.

- [ ] **Step 4: Run** `uv run pytest -v` → all PASS.

- [ ] **Step 5: Dockerfile** (`python:3.12-slim`, copy uv from `ghcr.io/astral-sh/uv:latest`, `uv sync --frozen --no-dev`, non-root user, `CMD uv run uvicorn app.main:app --host 0.0.0.0 --port 8001`) and compose services `auth-migrate` (command `uv run alembic upgrade head`, depends on postgres healthy) and `auth` (ports 8001, volume `./infra/keys:/keys`, depends on `auth-migrate` completed, healthcheck on `/health`).

- [ ] **Step 6: Verify** `docker compose up -d --build auth`, then `curl -s localhost:8001/.well-known/jwks.json` returns a key and a register→refresh round-trip works with `curl -c/-b`.

- [ ] **Step 7: Commit** `feat(auth): register, login, rotating refresh, logout, me, jwks`

---
### Task 4: API scaffold, JWT verification, user mirror, `/v1/me`

**Files:**
- Create: `services/api/pyproject.toml`, `services/api/app/main.py`, `services/api/app/core/config.py`, `services/api/app/core/security.py`, `services/api/app/core/errors.py`, `services/api/app/db/base.py`, `services/api/app/db/session.py`, `services/api/app/deps.py`, `services/api/app/services/users.py`, `services/api/app/routers/health.py`, `services/api/app/routers/me.py`, `services/api/Dockerfile`, `services/api/alembic.ini`, `services/api/alembic/env.py`, `services/api/tests/conftest.py`, `services/api/tests/jwt_utils.py`, `services/api/tests/test_auth_verification.py`
- Modify: `docker-compose.yml` (add `api-migrate`, `api`), `docker-compose.override.yml`

**Interfaces:**
- `Settings` (prefix `API_`): `env, database_url, auth_jwks_url, jwt_issuer, jwt_audience, web_origin, jwks_ttl_seconds=600, jwks_min_refetch_seconds=30`.
- `security.JWKSCache` with `async get_key(kid) -> RSAPublicKey | None` and `set_static(keys: dict[str, RSAPublicKey])` for tests; module-level `jwks_cache`. `async verify_access_token(token) -> Claims` where `Claims = TypedDict(sub: str, email: str, name: str)`; raises `AppError(401, "invalid_token")`.
- `deps.CurrentUser = Annotated[User, Depends(get_current_user)]` where `get_current_user` verifies the bearer token, upserts the mirror via `users.upsert_from_claims(session, claims) -> User`, and returns the `User` ORM row.
- `AppError(status: int, code: str, message: str = "", details: dict | None = None)` and handlers producing the error envelope; `NotFound = AppError(404, "not_found")` helper.
- Test helpers: `jwt_utils.TEST_KEY` (RSA key generated once), `jwt_utils.sign(sub: str, email: str, name: str, **overrides) -> str`, fixtures `user_a`, `user_b` (dicts with `id, email, name, headers`), `client`.
- HTTP: `GET /v1/me` → `{"user": {"id","email","name"}, "workspaces": []}` (workspaces filled in Task 6).

- [ ] **Step 1: Create the uv project** (same deps as auth minus argon2, plus `respx` in dev).

- [ ] **Step 2: Write failing tests**

```python
# test_auth_verification.py
async def test_me_requires_token(client):
    r = await client.get("/v1/me"); assert r.status_code == 401

async def test_me_mirrors_user(client, user_a, db_session):
    r = await client.get("/v1/me", headers=user_a["headers"])
    assert r.status_code == 200 and r.json()["user"]["email"] == user_a["email"]
    row = await db_session.get(User, uuid.UUID(user_a["id"]))
    assert row is not None and row.name == user_a["name"]

async def test_me_updates_changed_name(client, user_a):
    await client.get("/v1/me", headers=user_a["headers"])
    tok = sign(user_a["id"], user_a["email"], "Renamed")
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.json()["user"]["name"] == "Renamed"

async def test_wrong_audience_401(client, user_a):
    tok = sign(user_a["id"], user_a["email"], user_a["name"], aud="other")
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {tok}"}); assert r.status_code == 401

async def test_expired_401(client, user_a):
    tok = sign(user_a["id"], user_a["email"], user_a["name"], exp=int(time.time()) - 100)
    r = await client.get("/v1/me", headers={"Authorization": f"Bearer {tok}"}); assert r.status_code == 401

async def test_unknown_kid_triggers_refetch(respx_mock, monkeypatch):
    # cache starts empty; JWKS endpoint mocked to return TEST_KEY's jwk; verify succeeds and endpoint was called once
    ...
```

- [ ] **Step 3: Run** → FAIL.

- [ ] **Step 4: Implement** `security.py`:

```python
class JWKSCache:
    def __init__(self, url: str, ttl: int, min_refetch: int) -> None:
        self._url, self._ttl, self._min = url, ttl, min_refetch
        self._keys: dict[str, RSAPublicKey] = {}
        self._fetched_at = 0.0
        self._lock = asyncio.Lock()
        self._static = False

    def set_static(self, keys: dict[str, RSAPublicKey]) -> None:
        self._keys, self._static, self._fetched_at = dict(keys), True, time.monotonic()

    async def _fetch(self) -> None:
        async with httpx.AsyncClient(timeout=5) as c:
            data = (await c.get(self._url)).raise_for_status().json()
        self._keys = {k["kid"]: jwt.PyJWK(k).key for k in data["keys"]}
        self._fetched_at = time.monotonic()

    async def get_key(self, kid: str) -> RSAPublicKey | None:
        if self._static:
            return self._keys.get(kid)
        async with self._lock:
            stale = time.monotonic() - self._fetched_at > self._ttl
            unknown = kid not in self._keys and time.monotonic() - self._fetched_at > self._min
            if stale or unknown or not self._keys:
                try: await self._fetch()
                except httpx.HTTPError: pass
            return self._keys.get(kid)
```

`verify_access_token` reads `kid` with `jwt.get_unverified_header`, gets the key, then `jwt.decode(token, key, algorithms=["RS256"], audience=settings.jwt_audience, issuer=settings.jwt_issuer, leeway=10, options={"require": ["exp","iat","sub"]})`. `users.upsert_from_claims` runs `INSERT ... ON CONFLICT (id) DO UPDATE SET email=EXCLUDED.email, name=EXCLUDED.name, last_seen_at=now()` (postgres `insert(...).on_conflict_do_update`) and returns the row. Migration `0001_initial_schema` in this task creates ONLY `users` (mirror): `id uuid pk, email citext unique, name text, last_seen_at, created_at, updated_at`. Later tasks add migrations.

- [ ] **Step 5: Run** → PASS.

- [ ] **Step 6: Dockerfile + compose** (`api-migrate`, `api` on 8000 depending on `api-migrate` completed and `auth` healthy; healthcheck `/health`). Override file: bind mounts `./services/api:/app`, `./services/auth:/app`, `--reload`, `UV_CACHE_DIR=/tmp/uv`.

- [ ] **Step 7: Verify** `docker compose up -d --build`; register via auth with curl; call `GET localhost:8000/v1/me` with the access token → 200.

- [ ] **Step 8: Commit** `feat(api): scaffold with JWKS verification and user mirror`

---

### Task 5: API domain schema (migration + models)

**Files:**
- Create: `services/api/alembic/versions/0002_domain.py`, `services/api/app/models/__init__.py`, `services/api/app/models/workspace.py`, `services/api/app/models/project.py`, `services/api/app/models/session.py`, `services/api/app/models/risk.py`, `services/api/app/models/vote.py`, `services/api/app/models/grading.py`, `services/api/tests/test_schema.py`

**Interfaces:**
- Enums (Python `enum.StrEnum` mapped to PG enums): `WorkspaceRole(owner, admin, member)`, `ProjectStatus(planning, active, closed)`, `SessionPhase(collect, merge, vote, sealed)`, `RiskOrigin(participant, suggestion, surprise)`, `GradingOutcome(yes, no, partial)`.
- Models exactly as the spec's data model section: `Workspace`, `WorkspaceMember`, `Project` (with `tags: list[str]` via `ARRAY(Text)`, `search_text` generated stored column declared with `Computed("title || ' ' || description", persisted=True)`), `PremortemSession`, `SessionParticipant`, `Risk` (with `agg_*` nullable numerics), `Vote`, `Grading`.
- SQL view `graded_predictions` created in the migration with `op.execute` (columns: `vote_id, workspace_id, user_id, session_id, project_id, risk_id, probability, p, o, outcome, impact, tags, closed_at`).
- Indexes: as listed in the spec (GIN on `projects.tags`, `risks.tags`; GIN trgm on `projects.search_text`, `risks.statement`; partial `risks(session_id) WHERE duplicate_of IS NULL`; `votes(session_id,user_id)`, `votes(workspace_id,user_id)`; `gradings(project_id)`; `projects(workspace_id,status,created_at desc)`).
- Check constraints: `votes.probability BETWEEN 0 AND 100`, `votes.impact BETWEEN 1 AND 5`, `risks.duplicate_of <> id`, `(risks.origin='surprise') = (risks.session_id IS NULL)`, `(projects.status='closed') = (projects.closed_at IS NOT NULL)`, `(sessions.phase='sealed') = (sessions.sealed_at IS NOT NULL)`.

- [ ] **Step 1: Write failing test** `test_schema.py`: insert a workspace, project, session, risk, vote, grading through the ORM inside the rollback session; select from `graded_predictions` and assert one row with `p == 0.8` and `o == 0.5` for a `partial` grading; assert inserting `probability=101` raises `IntegrityError`.

- [ ] **Step 2: Run** → FAIL. **Step 3:** write models + migration. **Step 4:** run → PASS; also `uv run alembic upgrade head` on the dev DB and `alembic check` reports no drift.

- [ ] **Step 5: Commit** `feat(api): domain schema, models and graded_predictions view`

---

### Task 6: Workspaces, members, tags

**Files:**
- Create: `services/api/app/schemas/common.py`, `services/api/app/schemas/workspace.py`, `services/api/app/services/workspaces.py`, `services/api/app/routers/workspaces.py`, `services/api/tests/test_workspaces.py`
- Modify: `services/api/app/deps.py` (add `require_membership`), `services/api/app/routers/me.py` (fill `workspaces`), `services/api/app/main.py`

**Interfaces:**
- Schemas: `UserRef{id,email,name}`, `WorkspaceOut{id,name,slug,my_role,created_at}`, `WorkspaceCreate{name: str(1..120), slug: str | None}`, `MemberOut{user: UserRef, role, joined_at}`, `MemberAdd{email, role}`, `MemberRoleSet{role}`, `TagStat{tag, project_count, risk_count}`, `Page[T]{items, next_cursor}`.
- `deps.require_membership(workspace_id, user, session, min_role: WorkspaceRole = member) -> WorkspaceMember` raising 404 if not a member, 403 `insufficient_role` if role below `min_role`. Role order owner > admin > member.
- `workspaces.slugify(name) -> str` (lowercase, `[a-z0-9-]`, trimmed, max 50; on collision append `-2`, `-3`, ...).
- Routes (all under `/v1`): `POST /workspaces` (201; creator becomes owner), `GET /workspaces`, `GET /workspaces/{ws}`, `PATCH /workspaces/{ws}` (admin+), `GET /workspaces/{ws}/members`, `POST /workspaces/{ws}/members` (admin+; 404 `user_not_registered` if email unknown in mirror; 409 `already_member`; only owner may grant `owner`), `PUT /workspaces/{ws}/members/{user_id}` (409 `last_owner` when demoting the sole owner), `DELETE /workspaces/{ws}/members/{user_id}` (admin+ or self; 409 `last_owner`), `GET /workspaces/{ws}/tags` (`unnest(tags)` counts over projects and risks).

- [ ] **Step 1: Write failing tests**: create returns owner role and slug; list shows only mine; non-member GET → 404; member PATCH → 403; add member by unknown email → 404; add existing user → 201 with role; admin cannot grant owner (403); demote last owner → 409; self-leave as member → 204; tags endpoint counts after creating two projects sharing a tag (projects created via the service directly since Task 7 is not built yet).

- [ ] **Step 2–4:** run → FAIL; implement; run → PASS.

- [ ] **Step 5: Commit** `feat(api): workspaces, members, tags`

---

### Task 7: Projects

**Files:**
- Create: `services/api/app/schemas/project.py`, `services/api/app/services/projects.py`, `services/api/app/routers/projects.py`, `services/api/app/core/pagination.py`, `services/api/tests/test_projects.py`
- Modify: `main.py`

**Interfaces:**
- Schemas: `ProjectCreate{title(1..200), description="", tags: list[str]=[], planned_start: date|None, planned_end: date|None}` (validator normalizes tags: lowercase, strip, dedupe, max 20 × 40 chars; `planned_end >= planned_start`), `ProjectPatch` (all optional), `ProjectOut{id, workspace_id, title, description, tags, planned_start, planned_end, status, activated_at, closed_at, archived_at, created_by: UserRef, created_at, updated_at, session: SessionSummary|None}` where `SessionSummary{id, phase, sealed_at, fully_graded_at}`, `ProjectTransition{to: Literal["active","closed"]}`, `TransitionResult{project: ProjectOut, warnings: list[{code, count}]}`.
- `pagination.encode_cursor(created_at, id) / decode_cursor` (base64 of `iso|uuid`); lists ordered by `created_at desc, id desc`, default limit 25, max 100.
- `projects.load_for_member(session, project_id, user) -> tuple[Project, WorkspaceMember]` (404 if project missing or user not a member of its workspace) — reused by sessions/risks/gradings.
- `projects.transition(session, project, member, user, to) -> TransitionResult`: rules per spec state machine; `active → closed` requires `session.phase == sealed` if a session exists (409 `session_not_sealed`); `planning → closed` 409 `invalid_transition`; closing by non-facilitator non-admin 403.
- Routes: `POST|GET /workspaces/{ws}/projects` (`?status=&tag=&q=&include_archived=false&cursor=&limit=`; `q` uses `search_text % :q OR title ILIKE`), `GET|PATCH|DELETE /projects/{id}` (PATCH 409 `project_closed`; DELETE admin+, 409 `project_has_sealed_session`), `POST /projects/{id}/transition`, `POST /projects/{id}/archive`, `POST /projects/{id}/unarchive`.

- [ ] **Step 1: Write failing tests**: create normalizes tags (`" Vendor "` → `vendor`); list filters by status and tag; cursor pagination returns disjoint pages; `test_project_get_non_member_404`; PATCH after close → 409; `planning→active` sets `activated_at`; `planning→closed` → 409; delete with sealed session → 409 (seed a sealed session row directly); archive hides from list unless `include_archived=true`.

- [ ] **Step 2–4:** FAIL → implement → PASS. **Step 5: Commit** `feat(api): projects with transitions, archive, search and pagination`

---

### Task 8: Sessions, participants, risks (collect/merge)

**Files:**
- Create: `services/api/app/schemas/session.py`, `services/api/app/schemas/risk.py`, `services/api/app/services/sessions.py`, `services/api/app/services/risks.py`, `services/api/app/routers/sessions.py`, `services/api/app/routers/risks.py`, `services/api/tests/test_sessions.py`, `services/api/tests/test_risks.py`
- Modify: `main.py`

**Interfaces:**
- Schemas: `SessionOut{id, project_id, workspace_id, phase, facilitator: UserRef, created_by: UserRef, phase_changed_at, sealed_at, fully_graded_at, participants: list[UserRef], counts: {risks_total, risks_canonical, participants, voters_complete}, me: {is_facilitator, is_participant, risks_submitted, votes_cast, votes_required}}`, `SessionCreate{participant_ids: list[UUID] = []}`, `SessionPatch{facilitator_id}`, `SessionTransition{to}`, `SessionTransitionResult{session, incomplete_voters: list[UserRef]}`, `ParticipantsAdd{user_ids}`.
- `RiskOut{id, session_id, project_id, statement, tags, origin, duplicate_of, source_risk_id, author: UserRef|None, created_at, updated_at, aggregates: Aggregates|None, merged_from: list[{id, statement}], my_vote: {probability, impact}|None, grading: GradingOut|None}`; `RiskCreate{statement(3..500)}`, `RiskPatch{statement?, tags?, duplicate_of?: UUID|None}`, `RiskAdopt{source_risk_id, statement?, tags?}`, `RiskList{phase, items, submission_counts: list[{user: UserRef, count}]|None}`.
- `sessions.load_for_member(session, session_id, user) -> tuple[PremortemSession, Project, WorkspaceMember]`; `sessions.is_facilitator(sess, member, user) -> bool` (facilitator_id match or role admin+); `sessions.is_participant(sess, user) -> bool`.
- `sessions.transition(db, sess, user, to) -> SessionTransitionResult`; the `vote → sealed` branch calls `votes.seal(db, sess)` from Task 9 (stub raising `NotImplementedError` in this task, replaced in Task 9).
- `risks.visible_list(db, sess, user, is_fac, is_part) -> RiskList` applying the visibility matrix: collect → own risks only (facilitator additionally gets `submission_counts`); merge → facilitator sees all with `author`, others 403 `phase_not_visible`; vote → canonical only, `author=None`; sealed → canonical with aggregates and `merged_from`, `author` only for own risks.
- `risks.resolve_duplicate_root(db, session_id, target_id) -> UUID` (walk `duplicate_of`, max depth 50, reject cycles and cross-session targets with 400 `invalid_duplicate`).
- Routes: `POST /projects/{id}/session` (member; 409 `session_exists`, `project_closed`, `project_archived`), `GET|PATCH|DELETE /sessions/{id}`, `POST /sessions/{id}/transition`, `POST /sessions/{id}/participants`, `DELETE /sessions/{id}/participants/{user_id}` (409 `participant_has_votes`, `cannot_remove_facilitator`, `session_sealed`), `GET|POST /sessions/{id}/risks`, `PATCH|DELETE /risks/{id}`, `POST /sessions/{id}/risks/adopt` (facilitator, merge; `source_risk_id` must be a graded canonical risk in the same workspace; creates `origin=suggestion`).

- [ ] **Step 1: Write failing tests** (fixtures: `workspace` with `user_a` owner and `user_b` member; `project`; `session_collect` created by `user_a` with `user_b` as participant):
  - create auto-adds facilitator as participant; second create → 409.
  - in collect, `user_b` posts a risk; `user_a` GET risks sees only own items but `submission_counts` shows `user_b: 1`; `user_b` cannot edit `user_a`'s risk (404).
  - `collect→merge` with zero risks → 409 `no_risks`; with risks → phase `merge`.
  - in merge, `user_b` GET risks → 403; facilitator PATCH `duplicate_of` on a risk pointing at another → OK; pointing at itself → 400; cycle A→B, B→A → 400; chain flattening: mark C dup-of B where B dup-of A → response `duplicate_of == A`.
  - `merge→vote` freezes: PATCH statement in vote → 409 `phase_locked`.
  - `test_vote_phase_hides_author`: in vote, GET risks items all have `author is None` and no duplicates listed.
  - non-facilitator transition → 403; delete session in vote → 409.
  - PATCH facilitator by admin to `user_b` → `user_b` becomes participant and can transition.

- [ ] **Step 2–4:** FAIL → implement → PASS. **Step 5: Commit** `feat(api): pre-mortem sessions, participants and risk collection/merge`

---

### Task 9: Votes and seal aggregation

**Files:**
- Create: `services/api/app/schemas/vote.py`, `services/api/app/services/votes.py`, `services/api/app/routers/votes.py`, `services/api/tests/test_votes.py`
- Modify: `services/api/app/services/sessions.py` (wire `votes.seal`), `main.py`

**Interfaces:**
- Schemas: `VoteIn{risk_id, probability: int 0..100, impact: int 1..5}`, `VotesPut{votes: list[VoteIn]}`, `MyVotes{items: list[{risk_id, probability, impact, updated_at}], required: int}`, `Aggregates{vote_count, mean_probability, median_probability, probability_stddev, agreement, mean_impact, risk_score}`, `ResultsOut{session: SessionOut, risks: list[RiskOut + histogram: list[int]*10], participation: {participants, voters_complete, voters_partial, voters_none}}`.
- `votes.aggregate(probabilities: list[int], impacts: list[int]) -> Aggregates | None` (pure; None on empty; median = mean of middle two; population stddev; `agreement = max(0, min(1, 1 - stddev/50))`; `risk_score = mean_p/100 * mean_impact`, rounded to 2/3 decimals as in the spec).
- `votes.seal(db, sess) -> list[UserRef]` (incomplete voters): `SELECT risks FOR UPDATE`, compute and write `agg_*`, set `sealed_at`; the phase update itself is done by `sessions.transition` with the conditional `WHERE phase='vote'`.
- Routes: `GET /sessions/{id}/votes/me`, `PUT /sessions/{id}/votes` (participant, vote phase; 400 `unknown_risk` if any `risk_id` is not canonical in this session; bulk `INSERT ... ON CONFLICT (risk_id, user_id) DO UPDATE`), `GET /sessions/{id}/results` (member; 409 `not_sealed`).

- [ ] **Step 1: Write failing tests**:
  - `test_aggregate_example`: `aggregate([90,70,40,40],[3,4,2,5])` → `vote_count 4, mean 60, median 55, stddev ≈ 20.62, agreement ≈ 0.59, mean_impact 3.5, risk_score 2.1`.
  - PUT partial votes allowed; second PUT updates in place (row count unchanged); PUT in collect → 409; unknown risk id → 400; non-participant → 403.
  - `user_b` cannot see `user_a`'s votes through any endpoint before or after seal (`votes/me` returns only own).
  - seal with zero votes → 409 `no_votes`; seal returns `incomplete_voters` containing `user_b` when `user_b` voted on 1 of 2 risks; after seal `agg_mean_probability` matches; PUT after seal → 409.
  - `test_results_has_no_user_votes`: results JSON serialized contains no `user_id` keys and no per-user probability lists; `my_vote` present for the caller only.
  - `test_seal_twice_409`: run two `transition(to="sealed")` calls concurrently with `asyncio.gather` on two separate DB sessions against the committed fixture (this test uses a non-rollback connection and cleans up after); exactly one 200 and one 409.

- [ ] **Step 2–4:** FAIL → implement → PASS. **Step 5: Commit** `feat(api): hidden voting, seal aggregation and results`

---

### Task 10: Close-out: gradings, surprises, project report

**Files:**
- Create: `services/api/app/schemas/grading.py`, `services/api/app/services/grading.py`, `services/api/app/routers/grading.py`, `services/api/tests/test_grading.py`
- Modify: `main.py`, `services/api/app/services/risks.py` (surprise PATCH/DELETE rules)

**Interfaces:**
- Schemas: `GradingIn{risk_id, outcome: yes|no|partial, note: str = ""}`, `GradingsPut{gradings: list[GradingIn]}`, `GradingOut{outcome, note, graded_by: UserRef, updated_at}`, `SurpriseCreate{statement(3..500), tags: list[str] = []}`, `CloseoutOut{project: ProjectOut, session: SessionOut|None, risks: list[RiskOut], surprises: list[RiskOut], ungraded_count: int, possible_duplicates: list[{surprise_id, risk_id, similarity}]}`, `ProjectReport{project, session, summary: {n_canonical, n_graded, n_voters, expected_materialized, actual_materialized, project_brier, n_predictions}, risks: list[{risk_id, statement, tags, mean_predicted, agreement, mean_impact, outcome, miss, note}], surprises: list[{risk_id, statement, tags}], biggest_misses: list[...]}`.
- `grading.put_gradings(db, project, user, items)` (facilitator; session sealed; project active/closed; 400 `unknown_risk` for non-canonical or foreign risk ids; upsert; recompute `fully_graded_at` = now if every canonical risk has a grading else NULL).
- `grading.add_surprise(db, project, user, data) -> Risk` inserting `Risk(origin=surprise, session_id=None)` and `Grading(outcome=yes, note="")` in one transaction.
- `grading.possible_duplicates(db, project) -> list` via `similarity(surprise.statement, risk.statement) > 0.5`.
- Routes: `GET /projects/{id}/closeout`, `PUT /projects/{id}/gradings`, `DELETE /gradings/{risk_id}`, `POST /projects/{id}/surprises`, `GET /projects/{id}/report`; `PATCH|DELETE /risks/{id}` accept surprises for the facilitator regardless of phase.

- [ ] **Step 1: Write failing tests** (fixture `sealed_project`: project active with sealed session, 3 canonical risks, votes from `user_a` and `user_b`):
  - grading before seal → 409; grading by `user_b` (member, not facilitator) → 403; admin (owner `user_a` is facilitator anyway; add `user_c` admin) → OK.
  - PUT 2 of 3 gradings → `ungraded_count == 1`, `fully_graded_at is None`; PUT the third → set; DELETE one → cleared.
  - surprise creates a risk with `origin == "surprise"` and grading `yes`; it appears in `closeout.surprises`, never in `closeout.risks`.
  - `possible_duplicates` flags a surprise whose statement is near-identical to a canonical risk.
  - report: `expected_materialized == sum(mean_p/100)`, `actual_materialized == 1.5` for yes/partial/no, `biggest_misses[0]` is the risk with largest `|o - mean_p|`.
  - close project via `POST /projects/{id}/transition {to: closed}` with 1 ungraded → 200 with warning `ungraded_risks: 1`.

- [ ] **Step 2–4:** FAIL → implement → PASS. **Step 5: Commit** `feat(api): close-out grading, surprises and project report`

---
### Task 11: Calibration math and endpoints

**Files:**
- Create: `services/api/app/services/calibration.py`, `services/api/app/services/calibration_queries.py`, `services/api/app/schemas/calibration.py`, `services/api/app/routers/calibration.py`, `services/api/tests/test_calibration_math.py`, `services/api/tests/test_calibration_api.py`
- Modify: `main.py`

**Interfaces:**
- Constants module-level in `calibration.py`: `MIN_SCORE_N=10, MIN_BIN_N=5, MIN_TAG_N=10, BIN_COUNT=10, ROLLING_N=30, TREND_MIN_PTS=4, TREND_EPS=0.005, CALIBRATED_EPS=0.05, BLIND_SPOT_MAX_P=0.30`.
- `@dataclass Prediction(p: float, o: float, probability: int, impact: int, risk_id: UUID, project_id: UUID, closed_at: datetime, tags: list[str], user_id: UUID)`.
- Pure functions (no DB):
  - `brier(preds) -> float | None` (None if `len < MIN_SCORE_N`)
  - `brier_unchecked(preds) -> float` (used for per-project points; caller decides gating)
  - `brier_skill(preds, base_rate) -> float | None`
  - `bins(preds) -> list[Bin]` where `Bin{index, range: tuple[int,int], n, mean_predicted: float|None, observed: float|None, reliable: bool}`; always 10.
  - `bias(preds) -> tuple[float|None, str|None]` → labels `over_estimates_risk|under_estimates_risk|calibrated`.
  - `ece(bins) -> float | None`, `overconfidence(bins) -> tuple[float|None, str|None]` → `overconfident|underconfident|calibrated`.
  - `trend(preds) -> Trend{direction, slope, points: list[TrendPoint]}` with `TrendPoint{project_id, closed_at, n_project, brier_project, n_rolling, brier_rolling, brier_cumulative}`; direction via OLS slope on `brier_rolling`.
  - `worst_calls(preds, k=5) -> list[Prediction]` sorted by `(p-o)²` desc.
  - `summary(preds, base_rate) -> CalibrationSummary` bundling sample, brier, brier_skill, base_rate, bias(+label), ece, overconfidence(+label), bins, trend.
- `calibration_queries.load_predictions(db, workspace_id, user_id: UUID | None) -> list[Prediction]` from `graded_predictions`; `workspace_base_rate(db, ws) -> float`; `blind_spots(db, ws) / false_alarms(db, ws)`; `tag_stats(db, ws)`; `surprise_stats(db, ws)`; `member_stats(db, ws)`.
- Routes: `GET /workspaces/{ws}/calibration/me`, `GET /workspaces/{ws}/calibration/users/{user_id}` (self or admin+; 403 otherwise), `GET /workspaces/{ws}/calibration` (`members` only for admin+, else omitted).
- Response shapes `UserCalibration` and `WorkspaceCalibration` as in the spec.

- [ ] **Step 1: Write failing math tests**

```python
def P(prob, outcome, **kw):  # helper building Prediction
    o = {"yes": 1.0, "no": 0.0, "partial": 0.5}[outcome]
    return Prediction(p=prob/100, o=o, probability=prob, impact=3, risk_id=uuid4(), project_id=kw.get("project_id", uuid4()),
                      closed_at=kw.get("closed_at", datetime(2026,1,1,tzinfo=timezone.utc)), tags=kw.get("tags", []), user_id=uuid4())

EXAMPLE = [P(80,"yes"), P(30,"no"), P(60,"partial"), P(90,"no"), P(20,"yes")]

def test_brier_unchecked_worked_example():
    assert brier_unchecked(EXAMPLE) == pytest.approx(0.318)

def test_brier_null_under_min_n():
    assert brier(EXAMPLE) is None
    assert brier(EXAMPLE * 2) == pytest.approx(0.318)

def test_bias_worked_example():
    value, label = bias(EXAMPLE * 2)
    assert value == pytest.approx(0.06) and label == "over_estimates_risk"

def test_bins_always_ten_and_reliability():
    b = bins(EXAMPLE)
    assert len(b) == 10 and all(not x.reliable for x in b) and b[8].n == 1 and b[8].observed is None

def test_overconfidence_worked_example():
    # with MIN_BIN_N forced to 1 via monkeypatch, weighted signed gap is +0.26
    ...
    assert value == pytest.approx(0.26, abs=1e-6) and label == "overconfident"

def test_partial_counts_half():
    assert brier_unchecked([P(50, "partial")]) == 0.0

def test_trend_insufficient_then_improving():
    # 3 projects -> insufficient_data; 6 projects each with 10 preds whose error shrinks -> improving
    ...

def test_bins_edge_100_goes_to_last_bin():
    assert bins([P(100, "yes")])[9].n == 1
```

- [ ] **Step 2: Run** → FAIL. **Step 3:** implement pure functions (use `statistics.fmean`; OLS slope `cov(x,y)/var(x)` with `x = 0..n-1`). **Step 4:** PASS.

- [ ] **Step 5: Write failing API tests** (fixture builds 2 closed projects with sealed, graded sessions and 12 votes for `user_a`): `/calibration/me` returns `sample.n_graded == 12`, `brier` not None, 10 bins, `trend.points` length 2; `user_b` requesting `/calibration/users/{user_a}` → 403; admin → 200; workspace endpoint for member lacks `members`, for owner has it; blind spots include a risk graded `yes` with mean 15%; tag stats only for tags with ≥ 10 rows; surprise stats after adding 1 surprise → `n_surprises == 1`, `rate_per_project == 0.5`.

- [ ] **Step 6–7:** implement queries + router → PASS. **Step 8: Commit** `feat(api): calibration scoring and dashboards`

---

### Task 12: Suggestions

**Files:**
- Create: `services/api/app/services/suggestions.py`, `services/api/app/schemas/suggestion.py`, `services/api/app/routers/suggestions.py`, `services/api/tests/test_suggestions.py`
- Modify: `main.py`

**Interfaces:**
- Constants: `W_TAG=0.6, W_TEXT=0.4, MIN_PROJECT_SIM=0.15, MAX_SOURCE_PROJECTS=20, ALPHA=0.2, CLUSTER_SIM=0.55`.
- `suggestions.trigram_similarity(a: str, b: str) -> float` (pure Python pg_trgm-compatible: lowercase, collapse whitespace, pad words with two leading and one trailing space, 3-grams, Jaccard).
- `suggestions.cluster(items: list[SourceItem]) -> list[Cluster]` (pure; greedy; one member per project per cluster).
- `suggestions.suggest(db, workspace_id, title, description, tags, exclude_project_id, limit) -> SuggestionsOut{query: {tags, matched_projects}, suggestions: list[Suggestion]}` with `Suggestion{statement, score, materialization_rate, occurrences, mean_predicted_probability, tags, sources: list[{risk_id, project_id, project_title, project_similarity, outcome, mean_predicted_probability, origin, closed_at}]}`.
- SQL for similar projects and source risks exactly as in the spec (`SET LOCAL pg_trgm.similarity_threshold = 0.1` before the query).
- Routes: `GET /projects/{id}/suggestions?limit=`, `POST /workspaces/{ws}/suggestions {title, description?, tags?, exclude_project_id?}`.

- [ ] **Step 1: Write failing tests**: `trigram_similarity("Vendor API not ready", "vendor api not ready")` ≈ 1.0 and for unrelated strings < 0.2; `cluster` merges two near-identical statements from different projects and keeps two from the same project as one member; API: with three closed graded projects tagged `vendor` (risk "Vendor API not ready" graded yes in two, no in one) and one tagged `mobile`, `POST /suggestions {title: "New vendor integration", tags: ["vendor"]}` returns that statement first with `occurrences == 3`, `materialization_rate ≈ 0.667`, sources sorted by similarity, and excludes the mobile project; empty tags and empty title → `suggestions == []`; a surprise from a similar project appears with `origin == "surprise"`.

- [ ] **Step 2–4:** FAIL → implement → PASS. **Step 5: Commit** `feat(api): history-grounded risk suggestions`

---

### Task 13: Web scaffold, auth library, API client, login/register

**Files:**
- Create: `apps/web/*` scaffold (Next 15 + TS + Tailwind v4 + shadcn init), `apps/web/lib/env.ts`, `apps/web/lib/auth.ts`, `apps/web/lib/api.ts`, `apps/web/lib/auth-context.tsx`, `apps/web/lib/schemas.ts`, `apps/web/lib/utils.ts`, `apps/web/middleware.ts`, `apps/web/app/layout.tsx`, `apps/web/app/page.tsx`, `apps/web/app/(auth)/layout.tsx`, `apps/web/app/(auth)/login/page.tsx`, `apps/web/app/(auth)/register/page.tsx`, `apps/web/app/(app)/layout.tsx`, `apps/web/components/auth/LoginForm.tsx`, `apps/web/components/auth/RegisterForm.tsx`, `apps/web/components/auth/AuthGuard.tsx`, `apps/web/components/shell/AppShell.tsx`, `apps/web/vitest.config.ts`, `apps/web/vitest.setup.ts`, `apps/web/__tests__/api.test.ts`, `apps/web/__tests__/auth.test.ts`

**Interfaces:**
- `lib/auth.ts`: `getAccessToken(): string | null`, `setAccessToken(t: string | null)`, `refresh(): Promise<string | null>` (single in-flight promise), `login(email, password): Promise<User>`, `register(email, name, password): Promise<User>`, `logout(): Promise<void>`, `setSessionHint(on: boolean)` (writes/clears cookie `fs_session=1; Path=/; SameSite=Lax`). `User = {id, email, name}`.
- `lib/api.ts`: `apiFetch<T>(path: string, init?: {method?, body?: unknown, schema?: z.ZodType<T>}): Promise<T>`; throws `ApiError{status, code, message, details}`; on 401 calls `refresh()` once and retries; if refresh fails throws `UnauthorizedError` and dispatches `window.dispatchEvent(new Event("fs:unauthorized"))`.
- `lib/auth-context.tsx`: `AuthProvider` (on mount: `refresh()`; status `loading|authenticated|anonymous`; listens to `fs:unauthorized`), `useAuth(): {status, user, logout}`.
- `middleware.ts`: matcher `["/w/:path*"]` → redirect to `/login?next=` when cookie `fs_session` missing; `/login` and `/register` redirect to `/w` when present.
- shadcn components installed: button, card, input, label, form, select, slider, table, badge, tabs, dialog, sheet, sonner, separator, skeleton, textarea, dropdown-menu.

- [ ] **Step 1: Scaffold**: `npx create-next-app@latest apps/web --ts --tailwind --eslint --app --src-dir=false --import-alias "@/*" --use-npm`, `npx shadcn@latest init -d`, add the components above, `npm i @tanstack/react-query react-hook-form @hookform/resolvers zod recharts`, dev `vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event msw`.

- [ ] **Step 2: Write failing tests** `__tests__/api.test.ts` using msw: (a) attaches `Authorization: Bearer` from memory; (b) 401 → calls `POST /auth/refresh` with `credentials: include` → retries once with new token → resolves; (c) two concurrent 401s trigger exactly one refresh call; (d) refresh 401 → rejects with `UnauthorizedError` and dispatches `fs:unauthorized`; (e) non-2xx with error envelope → `ApiError.code` set. `__tests__/auth.test.ts`: `login` stores token and sets hint cookie; `logout` clears both.

- [ ] **Step 3: Run** `npm test` → FAIL. **Step 4:** implement `auth.ts`, `api.ts`, provider, guard, forms (react-hook-form + zod: email, password ≥ 8, name 1..80), pages, middleware, shell (sidebar: Projects, Members, Dashboard, Me; workspace switcher stub filled in Task 14; user menu with logout). **Step 5:** PASS; `npm run build` succeeds.

- [ ] **Step 6: Manual verify** against running auth service: register → lands on `/w`; reload keeps session; logout returns to `/login`; visiting `/w` logged out redirects.

- [ ] **Step 7: Commit** `feat(web): scaffold, auth library, api client, login and register`

---

### Task 14: Web workspaces, members, projects

**Files:**
- Create: `apps/web/lib/queries/workspaces.ts`, `apps/web/lib/queries/projects.ts`, `apps/web/lib/queries/suggestions.ts`, `apps/web/app/(app)/w/page.tsx`, `apps/web/app/(app)/w/[workspaceId]/layout.tsx`, `apps/web/app/(app)/w/[workspaceId]/page.tsx`, `apps/web/app/(app)/w/[workspaceId]/members/page.tsx`, `apps/web/app/(app)/w/[workspaceId]/p/new/page.tsx`, `apps/web/app/(app)/w/[workspaceId]/p/[projectId]/page.tsx`, `apps/web/components/workspace/WorkspaceCard.tsx`, `apps/web/components/workspace/CreateWorkspaceDialog.tsx`, `apps/web/components/workspace/MemberTable.tsx`, `apps/web/components/workspace/AddMemberForm.tsx`, `apps/web/components/project/ProjectCard.tsx`, `apps/web/components/project/ProjectForm.tsx`, `apps/web/components/project/TagInput.tsx`, `apps/web/components/project/StatusBadge.tsx`, `apps/web/components/project/TransitionButtons.tsx`, `apps/web/components/session/SuggestionsPanel.tsx`, `apps/web/components/project/ProjectReport.tsx`, `apps/web/__tests__/TagInput.test.tsx`, `apps/web/__tests__/SuggestionsPanel.test.tsx`

**Interfaces:**
- Query hooks: `useWorkspaces()`, `useWorkspace(id)`, `useCreateWorkspace()`, `useMembers(ws)`, `useAddMember(ws)`, `useSetRole(ws)`, `useRemoveMember(ws)`, `useProjects(ws, filters)`, `useProject(id)`, `useCreateProject(ws)`, `usePatchProject(id)`, `useTransitionProject(id)`, `useArchiveProject(id)`, `useSuggestions(ws, input, enabled)` (debounced 400 ms), `useProjectReport(id)`. Query keys: `["workspaces"]`, `["workspace", id]`, `["members", ws]`, `["projects", ws, filters]`, `["project", id]`, `["suggestions", ws, input]`, `["report", id]`.
- `WorkspaceContext` provided by `[workspaceId]/layout.tsx`: `{workspace, myRole, isAdmin}`.
- `SuggestionsPanel({workspaceId, title, description, tags, excludeProjectId?, onAdopt?})` renders each suggestion with statement, `materialized X of Y`, `predicted NN%`, source project titles, and a `surprise last time` badge when any source has `origin === "surprise"`; hides itself when `matched_projects === 0`.
- Page behaviours: overview groups projects by status and lists "Needs grading" (closed projects with `session.fully_graded_at === null`); project page shows status transitions (activate/close with confirm; close disabled with tooltip when session not sealed), a session card (create session / open session), the close-out link once sealed, and `ProjectReport` when closed.

- [ ] **Step 1: Write failing tests**: `TagInput` normalizes `" Vendor "` to `vendor` on Enter and prevents duplicates; `SuggestionsPanel` renders nothing when `matched_projects` is 0 and renders the surprise badge when a source has `origin: "surprise"` (msw-mocked `POST /v1/workspaces/:ws/suggestions`).
- [ ] **Step 2–4:** FAIL → implement → PASS; `npm run build` clean. **Step 5: Manual verify** end to end against the API. **Step 6: Commit** `feat(web): workspaces, members, projects and suggestions panel`

---

### Task 15: Web session page and close-out page

**Files:**
- Create: `apps/web/lib/queries/sessions.ts`, `apps/web/lib/queries/grading.ts`, `apps/web/app/(app)/w/[workspaceId]/p/[projectId]/session/page.tsx`, `apps/web/app/(app)/w/[workspaceId]/p/[projectId]/closeout/page.tsx`, `apps/web/components/session/PhaseStepper.tsx`, `apps/web/components/session/CollectView.tsx`, `apps/web/components/session/MergeView.tsx`, `apps/web/components/session/VoteView.tsx`, `apps/web/components/session/VoteRow.tsx`, `apps/web/components/session/SealedView.tsx`, `apps/web/components/session/ParticipantsDialog.tsx`, `apps/web/components/grading/GradingTable.tsx`, `apps/web/components/grading/SurprisesPanel.tsx`, `apps/web/__tests__/VoteRow.test.tsx`, `apps/web/__tests__/GradingTable.test.tsx`

**Interfaces:**
- Hooks: `useSession(id)` (refetchInterval 5000 while phase !== sealed so participants see phase changes), `useCreateSession(projectId)`, `useTransitionSession(id)`, `useRisks(sessionId)`, `useCreateRisk`, `usePatchRisk`, `useDeleteRisk`, `useAdoptRisk`, `useMyVotes(sessionId)`, `usePutVotes(sessionId)` (debounced autosave 600 ms after last slider change; shows `Saved N of M`), `useResults(sessionId)`, `useCloseout(projectId)`, `usePutGradings(projectId)`, `useAddSurprise(projectId)`, `useDeleteRisk`.
- `VoteRow({risk, value, onChange})`: slider 0..100 with numeric mirror input, impact as 5 radio dots; keyboard accessible; controlled.
- `MergeView`: table of all risks with author, inline statement edit, tag editor, "mark duplicate of" select (canonical risks only), delete, plus a `SuggestionsPanel` with `onAdopt` calling `useAdoptRisk`; "Advance to vote" button.
- `SealedView`: results table with mean/median/agreement bar, impact, risk score, tiny 10-bar histogram, `Your vote` column, `merged_from` expander.
- `GradingTable({risks, value, onChange})`: yes/no/partial segmented control + note per risk; `SurprisesPanel`: list + add form with tags, shows `possible_duplicates` hint.

- [ ] **Step 1: Write failing tests**: `VoteRow` keeps slider and number in sync and clamps 0..100; `GradingTable` emits the updated grading map when an outcome is chosen and shows `Graded N of M`.
- [ ] **Step 2–4:** FAIL → implement → PASS. **Step 5: Manual verify** the full two-browser flow from the spec's walkthrough. **Step 6: Commit** `feat(web): session phases, voting and close-out grading`

---

### Task 16: Web dashboards

**Files:**
- Create: `apps/web/lib/queries/calibration.ts`, `apps/web/app/(app)/w/[workspaceId]/dashboard/page.tsx`, `apps/web/app/(app)/w/[workspaceId]/me/page.tsx`, `apps/web/components/charts/StatTile.tsx`, `apps/web/components/charts/ReliabilityDiagram.tsx`, `apps/web/components/charts/BrierTrend.tsx`, `apps/web/components/charts/TagBiasChart.tsx`, `apps/web/components/charts/chartTheme.ts`, `apps/web/components/dashboard/BlindSpotsList.tsx`, `apps/web/components/dashboard/MembersTable.tsx`, `apps/web/components/dashboard/SampleNotice.tsx`, `apps/web/__tests__/ReliabilityDiagram.test.tsx`

**Interfaces:**
- Hooks: `useMyCalibration(ws)`, `useUserCalibration(ws, userId)`, `useWorkspaceCalibration(ws)`.
- `ReliabilityDiagram({bins})`: Recharts `ScatterChart` with a diagonal `ReferenceLine`, dot radius scaled by `n` (min 4, max 14), unreliable bins drawn hollow, tooltip `predicted / observed / n`; `BrierTrend({points})`: `LineChart` of `brier_rolling` with `brier_project` as faint dots, x = project title; `TagBiasChart({tags})`: horizontal `BarChart` of `bias` with diverging colours; `StatTile({label, value, hint, tone})`; `SampleNotice({sample})` explains "N of 10 predictions graded" when insufficient.
- Follow the `dataviz` skill (load it before writing chart code): single palette in `chartTheme.ts` using CSS variables, light/dark safe, no more than 6 categorical colours.

- [ ] **Step 1: Write failing test**: `ReliabilityDiagram` renders 10 points (query `[data-testid="bin-dot"]`) and marks unreliable ones with `data-reliable="false"` (ResizeObserver stubbed in `vitest.setup.ts`).
- [ ] **Step 2–4:** FAIL → implement → PASS; `npm run build` clean. **Step 5: Commit** `feat(web): calibration dashboards`

---

### Task 17: Seed script

**Files:**
- Create: `scripts/seed.py` (runs inside the api container: `docker compose run --rm -e AUTH_URL=http://auth:8001 api uv run python /app/scripts/seed.py`; compose mounts `./scripts:/app/scripts:ro`), `services/api/tests/test_seed_smoke.py`

**Interfaces:**
- `seed.main(auth_url: str, database_url: str, rng_seed: int = 42) -> None`; idempotent (returns early if workspace slug `demo` exists).
- Behaviour: registers `ada@demo.local`, `grace@demo.local`, `linus@demo.local` (password `demo1234`) via `POST {auth_url}/auth/register` (on 409 `email_taken`, logs in instead to obtain the `sub`); inserts mirror users; workspace "Demo Team" slug `demo`, Ada owner, others members; four closed projects ("Checkout Rewrite", "Data Warehouse Migration", "Mobile Launch", "SSO Rollout") with `closed_at` spread over the last 6 months, each with a sealed session, 8 canonical risks (statements drawn from a curated list per tag), votes from all three users using personas (Ada: p ≈ true rate ± 10; Grace: states 80–95 where outcomes hit ~55%; Linus: states 20–40 where outcomes hit ~60%), gradings, 1–2 surprises per project, `agg_*` computed with `votes.aggregate`; one active project "Q4 Platform Hardening" with a `collect` session where Ada and Grace have each submitted one risk.
- Prints credentials and the workspace URL.

- [ ] **Step 1: Write failing smoke test**: run `seed.main` against the test DB with a stubbed auth (monkeypatch `seed.register_user` to return fixed UUIDs); assert 5 projects, 4 sealed sessions, `graded_predictions` has ≥ 90 rows, and Ada's `brier_unchecked` is lower than Grace's.
- [ ] **Step 2–4:** FAIL → implement → PASS. **Step 5: Verify** from a clean volume: `docker compose down -v && docker compose up -d --build && docker compose run --rm api uv run python /app/scripts/seed.py`; log in as Ada; dashboard shows data. **Step 6: Commit** `feat: demo seed data`

---

### Task 18: Web Dockerfile, Playwright, README

**Files:**
- Create: `apps/web/Dockerfile`, `apps/web/playwright.config.ts`, `apps/web/e2e/auth.spec.ts`, `apps/web/e2e/session-flow.spec.ts`, `apps/web/e2e/dashboard.spec.ts`
- Modify: `docker-compose.yml` (add `web`), `docker-compose.override.yml`, `README.md`, `apps/web/next.config.ts` (`output: "standalone"`)

**Interfaces:**
- `web` service: multi-stage `node:22-alpine`, build args `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_AUTH_URL`, port 3000, depends on `api` and `auth`.
- Playwright `baseURL` from `E2E_BASE_URL` (default `http://localhost:3000`), no `webServer`; `npm run e2e` documented as "requires `docker compose up` and seed".
- e2e flows: (1) register a unique user → `/w` → reload stays logged in → logout → `/w` redirects to `/login`; (2) as Ada: create workspace → project → session → add 2 risks → advance to merge → advance to vote → vote → seal → results visible; (3) as Ada in `demo`: open dashboard → Brier tile shows a number and reliability diagram has 10 dots.

- [ ] **Step 1:** Dockerfile + compose `web`; `docker compose up -d --build web` serves `/login`.
- [ ] **Step 2:** write the three specs; run `npx playwright install chromium`; `npm run e2e` → PASS against the running stack.
- [ ] **Step 3:** README quick start: prerequisites, `cp .env.example .env`, `docker compose up -d --build`, seed command, credentials, native dev commands per service, test commands, OneDrive note, port fallback.
- [ ] **Step 4: Commit** `feat: web container, e2e smoke tests, README quick start`

---

## Self-review notes

- Spec coverage: workspaces/members (T6), projects (T7), sessions/risks (T8), votes/seal/results (T9), gradings/surprises/report (T10), calibration (T11), suggestions (T12), auth service (T2–T3), JWT verification and mirror (T4), schema/view (T5), web auth (T13), web pages (T14–T16), compose/seed/e2e/README (T1, T17, T18). Invites are intentionally out of scope (members are added by email of a registered user).
- Type consistency: `RiskOut`, `SessionOut`, `Aggregates`, `GradingOut` are defined in T8–T10 and reused by T11/T14–T16 hooks; `votes.aggregate` from T9 is reused by the seed in T17; `brier_unchecked` from T11 is reused by T17's smoke test.
- Review Focus items are pinned to tests in T3, T7, T8, T9, T11.
