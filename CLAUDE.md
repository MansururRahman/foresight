# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Foresight is a pre-mortem calibration engine: participants privately predict project risks and their probabilities, a facilitator grades them at close-out, and the app scores each person's and the team's calibration over time. Design spec: `docs/superpowers/specs/2026-09-25-foresight-design.md`; implementation plan: `docs/superpowers/plans/2026-09-25-foresight.md`.

## Commands

Whole stack in Docker (web on :3000, api on :8000, auth on :8001, Postgres on host port 5433):

```bash
cp .env.example .env
docker compose up -d --build
docker compose run --rm api python -m app.seed   # demo data; log in as ada@demo.local / demo1234
```

The `postgres` service must be running for the Python test suites (`docker compose up -d postgres`). Tests run against the `foresight_api_test` / `foresight_auth_test` databases. The api conftest downgrades to base and upgrades to head once per session, then rolls back each test's transaction.

```bash
# Python services (run from services/api or services/auth; Python 3.12 via uv)
uv sync
uv run pytest                                         # full suite
uv run pytest tests/test_votes.py::test_name -q       # single test
uv run ruff check . && uv run ruff format .
uv run mypy app                                       # strict mode
uv run alembic upgrade head                           # needs *_DATABASE_URL pointing at localhost:5433
uv run alembic revision -m "..."                      # migrations are hand-written, numbered 000N_*

# Web (apps/web); install with --legacy-peer-deps
npm install --legacy-peer-deps
npm run dev
npm test                                              # vitest run, __tests__/**/*.test.ts(x)
npx vitest run __tests__/VoteRow.test.tsx             # single file (add -t "name" for one test)
npm run lint && npm run typecheck
npm run e2e                                           # playwright; needs the running, seeded stack
```

The root `package.json` has shortcuts: `npm run test` (all three suites), `test:api`, `test:auth`, `test:web`, `dev:*`, `e2e`. The README has the env vars for running the services natively. Prefer a `.env.local` next to each `pyproject.toml` over exporting variables.

## Architecture

There are three services and one Postgres instance holding two isolated databases (`foresight_auth`, `foresight_api`), created by `infra/postgres/init/`.

- **services/auth** (FastAPI): registration, login, argon2 hashing, RS256 access tokens, rotating refresh tokens in an httpOnly cookie with reuse detection, and JWKS at `/.well-known/jwks.json`. The signing key comes from `infra/keys/dev_private.pem`, which `scripts/gen-keys.py` generates and git ignores.
- **services/api** (FastAPI, async SQLAlchemy 2): the domain. It **never reads the auth DB**. It verifies bearer tokens against the cached JWKS (`app/core/security.py`) and upserts a local `users` mirror from the token claims (`deps.get_current_user` → `services/users.upsert_from_claims`).
- **apps/web** (Next.js 16 App Router, Tailwind v4, shadcn/ui on `@base-ui/react`, TanStack Query, zod). **This Next.js version has breaking changes: read `apps/web/AGENTS.md` and `node_modules/next/dist/docs/` before writing web code.** For example, middleware is `proxy.ts`, not `middleware.ts`.

### API layering (`services/api/app`)

`routers/` are thin: they load the resource and check access, then call `services/`. Services hold the business rules and call `db.commit()` themselves. `schemas/` holds the Pydantic I/O models and `models/` the ORM. Conventions to follow:

- Errors are raised as `AppError(status, code, message)` and rendered as `{"error": {"code", "message", "details"}}`. The web `ApiError` reads that envelope.
- Access control: `deps.require_membership` returns **404 to non-members** (so existence never leaks) and 403 when the role is too low. Roles are ordered by `ROLE_ORDER` (member < admin < owner). A session's facilitator, or any admin, counts as facilitator (`sessions.is_facilitator`).
- Postgres enums are created by migrations and mapped with `pg_enum(..., create_type=False)`.
- `services/calibration.py` is pure math with no DB access, and its thresholds are named constants at the top of the file. `calibration_queries.py` loads the data it works on.

### Domain flow and privacy invariants

A project moves `planning → active → closed` and can also be archived, which freezes it. Its single pre-mortem session moves `collect → merge → vote → sealed` (`sessions.NEXT_PHASE`):

- **collect**: each participant sees only their own risks, plus submission counts.
- **merge**: the facilitator deduplicates. Canonical risks are those with `duplicate_of IS NULL`.
- **vote**: each participant sees only their own probability/impact votes.
- **sealed**: only aggregates are exposed (`votes.seal`, `votes.results`).

**Individual votes are never exposed to other users.** Many tests in `services/api/tests` enforce these rules, so keep them passing when changing risk, vote or results endpoints. Outside the allowed phase, mutations return `409 phase_locked`.

At close-out, gradings (`yes` / `partial` / `no` → 1 / 0.5 / 0) are recorded per canonical risk, and "surprises" (risks nobody predicted) are added. Calibration (Brier, reliability bins, bias, overconfidence, trend, per-tag stats, blind spots) is computed from graded predictions. Suggestions for new projects cluster past risks with trigram similarity.

### Web auth model

The access token lives only in memory (`lib/auth.ts`). The refresh token is an httpOnly cookie on the auth origin, and a non-httpOnly `fs_session` hint cookie lets `proxy.ts` do optimistic redirects. `lib/api.ts` (`apiFetch`) attaches the bearer token and, on a 401, does one silent refresh and retries. If that refresh fails, it dispatches `fs:unauthorized`, which `AuthProvider` handles. Server-state hooks live in `lib/queries/*.ts`, each with its own query-key factory. `useSession` polls every 5s until the session is sealed.

## Environment notes

- The repo sits in a OneDrive-synced folder. Keep `node_modules`, `.next`, `.venv` and uv caches out of sync.
- Inside Docker the DB host is `postgres:5432`; from the host it is `localhost:5433`.
