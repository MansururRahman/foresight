# Foresight

A pre-mortem calibration engine for teams.

Before a project starts, participants privately predict how it could fail and how likely each failure is. When the project closes, the facilitator grades each prediction against what actually happened. Over many projects, Foresight scores each person's and the team's calibration (Brier score, reliability curve, bias, overconfidence, trend), surfaces blind spots and chronic mis-estimation by tag, and suggests risks for new projects from the team's own history of what really materialized.

Nothing in this loop can be replaced by a chatbot: it depends on several people submitting simultaneously without seeing each other, sealed aggregates, outcomes recorded months later, and the organisation's own private history.

Design spec: [docs/superpowers/specs/2026-09-25-foresight-design.md](docs/superpowers/specs/2026-09-25-foresight-design.md) · Implementation plan: [docs/superpowers/plans/2026-09-25-foresight.md](docs/superpowers/plans/2026-09-25-foresight.md)

## Architecture

| Service | Stack | Port | Responsibility |
|---|---|---|---|
| `apps/web` | Next.js 16 (App Router), TypeScript, Tailwind v4, shadcn/ui, TanStack Query | 3000 | UI. Access token in memory, silent refresh, redirects via `proxy.ts` |
| `services/api` | FastAPI, SQLAlchemy 2 (async), Alembic, PyJWT | 8000 | Workspaces, projects, pre-mortem sessions, hidden voting, grading, calibration, suggestions |
| `services/auth` | FastAPI, argon2, RS256 JWT, JWKS | 8001 | Registration, login, rotating refresh cookies, token issuance |
| `postgres` | Postgres 16 with `pg_trgm` and `citext` | 5433 on the host | Two isolated databases: `foresight_auth` and `foresight_api` (plus `_test` twins) |

The API verifies access tokens with the auth service's public keys (JWKS, cached) and never reads the auth database. Individual votes are never exposed to other users; only sealed aggregates are.

## Quick start (Docker)

Prerequisites: Docker Desktop.

```bash
cp .env.example .env
docker compose up -d --build
docker compose run --rm api python -m app.seed
```

Open http://localhost:3000 and sign in with `ada@demo.local` / `demo1234` (also `grace@demo.local` and `linus@demo.local`, same password). Ada is the workspace owner. The demo workspace has four closed, graded projects and one live pre-mortem in the collect phase.

Host port 5433 is used for Postgres because 5432 is often taken by a local install; change `POSTGRES_HOST_PORT` in `.env` if needed.

## What to try

1. **Dashboard** in the demo workspace: Brier score, reliability diagram, trend, blind spots, chronic bias by tag, surprise rate. Compare **Me** as Ada (calibrated), Grace (overconfident) and Linus (hedging).
2. **New project** tagged `vendor`: the suggestions panel lists risks from similar past projects with how often they came true, and flags ones that were surprises last time.
3. **Run a pre-mortem** with two browsers signed in as two users: collect (nobody sees anyone else's risks), merge, vote (nobody sees anyone else's numbers), seal (aggregates appear), close the project, grade, and watch the dashboards update.

### Design-partner applications

The landing page at `/` stores applications in the api database. Export them as CSV:

```bash
docker compose run --rm api python -m app.leads export > leads.csv
docker compose run --rm api python -m app.leads export --status new > new-leads.csv
```

## Native development

Run Postgres in Docker and the services natively for fast reloads.

```bash
docker compose up -d postgres

# auth (services/auth)
cd services/auth && uv sync && AUTH_DATABASE_URL=postgresql+asyncpg://foresight_auth:auth_dev_pw@localhost:5433/foresight_auth uv run alembic upgrade head
AUTH_DATABASE_URL=postgresql+asyncpg://foresight_auth:auth_dev_pw@localhost:5433/foresight_auth AUTH_JWT_PRIVATE_KEY_FILE=../../infra/keys/dev_private.pem uv run uvicorn app.main:app --reload --port 8001

# api (services/api)
cd services/api && uv sync && API_DATABASE_URL=postgresql+asyncpg://foresight_api:api_dev_pw@localhost:5433/foresight_api uv run alembic upgrade head
API_DATABASE_URL=postgresql+asyncpg://foresight_api:api_dev_pw@localhost:5433/foresight_api API_AUTH_JWKS_URL=http://localhost:8001/.well-known/jwks.json uv run uvicorn app.main:app --reload --port 8000

# web (apps/web)
cd apps/web && npm install --legacy-peer-deps && npm run dev
```

Python 3.12 is pinned; `uv python install 3.12` provisions it. Put per-service overrides in a `.env.local` next to each `pyproject.toml` instead of exporting variables.

## Tests

```bash
cd services/auth && uv run pytest      # auth: register, login, rotation, reuse detection, jwks
cd services/api  && uv run pytest      # api: 122 tests incl. calibration math and privacy rules
cd apps/web      && npm test           # vitest: api client, auth library, components
cd apps/web      && npm run e2e        # playwright, against a running seeded stack
```

The Python suites need the Docker Postgres running (they use the `_test` databases with per-test rollback). Playwright needs `npx playwright install chromium` once.

## Repository layout

```
apps/web            Next.js app (app/, components/, lib/, __tests__/, e2e/)
services/api        FastAPI domain API (app/, alembic/, tests/)
services/auth       FastAPI auth service (app/, alembic/, tests/)
infra/postgres      DB init script (roles, databases, extensions)
infra/keys          Dev RSA signing key (generated, git-ignored)
scripts/            gen-keys.py, seed.py wrapper
docs/superpowers    Design spec and implementation plan
```

## Note on OneDrive

If this repository lives inside a OneDrive-synced folder, exclude `node_modules`, `.next`, `.venv` and uv caches from sync (or move the repo out of OneDrive). Postgres data lives in a named Docker volume and is never bind-mounted.
