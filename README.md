# Foresight

A pre-mortem calibration engine for teams.

Before a project starts, participants privately predict how it could fail and how likely each failure is. When the project closes, the facilitator grades each prediction against what actually happened. Over many projects, Foresight scores each person's and the team's calibration (Brier score, reliability curve, bias, overconfidence, trend), surfaces blind spots, and suggests risks for new projects from the team's own history of what really materialized.

Design spec: [docs/superpowers/specs/2026-09-25-foresight-design.md](docs/superpowers/specs/2026-09-25-foresight-design.md)

## Services

| Service | Stack | Port |
|---|---|---|
| `apps/web` | Next.js (App Router, TypeScript) | 3000 |
| `services/api` | FastAPI, SQLAlchemy 2 (async), Alembic | 8000 |
| `services/auth` | FastAPI, argon2, RS256 JWT + JWKS | 8001 |
| `postgres` | Postgres 16 (two isolated databases) | 5432 |

## Quick start

Quick-start instructions are added as the services land. See the spec for the build sequence.

## Note on OneDrive

If this repository lives inside a OneDrive-synced folder, exclude `node_modules`, `.next`, `.venv` and `.uv-cache` from sync (or move the repo out of OneDrive). Postgres data lives in a named Docker volume and is never bind-mounted.
