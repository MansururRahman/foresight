# Foresight — pre-mortem calibration engine

## Context

The user asked for a genuinely novel app (nothing equivalent exists), built on Next.js + Python + Postgres with frontend, API and authentication as three separate services. Commercial viability is irrelevant; novelty and a complete working MVP are the goal. The working directory `D:\Users\YOGA\OneDrive - Netpower AS\Repo\app_5k_c` is empty.

Market check: pre-mortems exist only as meeting templates (Asana, Instagantt, Miro); assumption/risk tracking exists only as RAID spreadsheet rows. No product closes the loop of **predicted risk → graded outcome → calibration score → suggestions for the next project**. That loop is Foresight.

Decisions already made with the user:
- Idea: **Foresight** (pre-mortem calibration engine).
- Auth: **custom FastAPI auth service** (argon2, rotating refresh tokens, RS256 JWTs, JWKS).
- Suggestions: **deterministic only** (pg_trgm + tag Jaccard). No LLM.
- Scope: **complete MVP**: workspaces, projects, sessions with private-then-reveal phases, probability voting, close-out grading, per-user and per-workspace calibration dashboards, similar-project risk suggestions, Docker Compose, seed data.

## Research and rationale

### Brief as understood

- **User's words:** build a genuinely novel app that has no existing equivalent in its domain, on Next.js + Python + Postgres, with frontend, backend and authentication as separate services. Selling it does not matter. The user acts as client; Claude acts as market researcher and senior developer.
- **Assumptions made:** a small-team web app is the right shape; the deliverable is a complete working MVP, not a platform; it runs locally with Docker Compose; no external paid services.

### Candidate ideas considered

Four niches were shortlisted because each is a well-known practice that today lives only in templates or spreadsheets, with no dedicated product closing the loop over time:

1. **Foresight: pre-mortem calibration engine (chosen).** Teams predict failure modes with probabilities before a project, grade them at close-out, and the app scores calibration across projects and suggests risks from the organisation's own history.
2. **Premise: living assumption register.** Assumptions with owner, confidence, expiry, and a dependency graph to decisions; shows blast radius when one is invalidated.
3. **Fresh Eyes: self-healing onboarding FAQ.** New hires log confusions; once resolved they write the answer; the next hire inherits a living FAQ and a confusion heat map.
4. **Reckon: personal estimate calibration trainer.** Log estimates with 90% intervals, log actuals, get a personal calibration curve and fudge factor per category.

### Market check (September 2026)

- **Pre-mortems** exist only as meeting templates and guides: [Asana premortem](https://asana.com/resources/premortem), [Asana template](https://asana.com/templates/premortem), [Mountain Goat Software](https://www.mountaingoatsoftware.com/agile/use-a-pre-mortem-to-identify-project-risks-before-they-occur), [Cognitive Bias Lab](https://www.cognitivebiaslab.com/pre-mortem/), [ActiveCollab](https://activecollab.com/blog/project-management/project-pre-mortem-analysis), [projectmanagers.net templates](https://projectmanagers.net/13-free-x-pre-mortem-template-excel-google-pdf/), [mymap.ai](https://www.mymap.ai/template/pre-mortem). None track predicted risks against actual outcomes across projects, and none score calibration.
- **Assumption tracking** exists only as RAID log rows: [Asana RAID log](https://asana.com/resources/raid-log). No product models assumption expiry or dependency blast radius.
- **Onboarding confusion capture** exists only as one-off surveys: [Formbricks](https://formbricks.com/blog/new-hire-onboarding-survey-questions), [PowerToFly](https://powertofly.com/up/new-hire-onboarding-survey-questions), [Enboarder](https://enboarder.com/blog/onboarding-survey-questions/). No product turns confusions into a living FAQ.
- **Estimate calibration** tooling exists only as statistics packages ([EmpiricalCalibration for R](https://ohdsi.github.io/EmpiricalCalibration/)) and calibration-trivia games ([LessWrong](https://www.lesswrong.com/posts/5XBv2onWGRKFtAEMN/link-how-to-calibrate-your-confidence-intervals)), not for real work estimates.

### Why Foresight was recommended and chosen

- It has the strongest novelty: the predicted-versus-actual loop with calibration scoring does not exist anywhere in the pre-mortem space.
- It is inherently multi-user and stateful (hidden submissions, sealed votes, outcomes recorded later), so it cannot be replaced by a chat assistant (see the next section).
- The math is well-defined (Brier score, reliability diagrams, expected calibration error), which makes the core testable without any external service.
- It fits the required three-service architecture naturally: auth, domain API, and a rich frontend with dashboards.

### Decision log (answers from the user)

| Question | Answer |
|---|---|
| Which idea | Foresight |
| Auth service | Custom FastAPI auth service (argon2, rotating refresh tokens, RS256 JWTs, JWKS) |
| Risk suggestions | Deterministic only (pg_trgm + tag overlap), no LLM |
| First version size | Complete MVP (workspaces, sessions with phases, voting, grading, dashboards, suggestions, Compose, seed) |
| Acceptance condition | Functionality must not be achievable with a general-purpose chatbot |

## Acceptance criterion: not reproducible with ChatGPT / Gemini / Copilot

The user accepts the plan only if the functionality cannot be achieved with a general-purpose chatbot. Feature-by-feature check:

| Feature | Chatbot can do it? | Why not |
|---|---|---|
| Brainstorm a list of plausible risks for a project | **Yes** | This is the one overlap. Foresight deliberately does NOT do this; it has no LLM. |
| Private, simultaneous risk submission by several people who cannot see each other's entries until the facilitator advances the phase | No | A chat is single-user and has no shared state, roles, or phase gates. |
| Hidden probability + impact voting, sealed and frozen aggregates, agreement/spread per risk | No | Requires multi-user persistence, concurrency control, and immutable records. |
| Grading outcomes months later against the exact predictions made earlier | No | No durable memory of who predicted what, when. |
| Brier score, calibration curve, bias, overconfidence, trend per person, computed from that person's real votes across many projects | No | Needs the longitudinal dataset above. A chatbot can explain the math but has no data to apply it to. |
| Workspace blind spots, per-tag chronic mis-estimation, surprise rate | No | Aggregations over an organisation's own history. |
| Suggest risks weighted by how often they actually materialized in this organisation's similar past projects, with provenance | No | Grounded in private outcome data the chatbot never has; a chatbot's suggestions are generic priors. |

Design consequence: every feature in scope is on the "No" side. The one "Yes" (free-text risk generation) is intentionally excluded so the product is defined by the loop a chatbot cannot close: **predict → seal → grade → score → learn**.

## Product in one paragraph

A workspace has members. A project gets a **pre-mortem session** before it starts. In phase `collect`, participants privately submit risk statements (nobody sees others' risks, to avoid anchoring). In `merge`, the facilitator dedupes and tags them. In `vote`, everyone privately assigns each canonical risk a probability (0–100) and impact (1–5). On `seal`, aggregates are frozen and revealed. When the project closes, the facilitator **grades** each risk (yes / no / partial) and records **surprises** (things that happened that nobody predicted). From graded votes the app computes Brier score, calibration curve, bias (pessimist/optimist), overconfidence, and trend per user and per workspace, plus blind spots, per-tag chronic mis-estimation, and surprise rate. When a new project is created, the app **suggests risks** from similar past projects, weighted by how often they actually materialized.

## Preview: what the finished app looks like

Visual style: clean, light/dark aware, Tailwind + shadcn/ui, left sidebar shell with workspace switcher. Charts follow the `dataviz` skill palette. Below are wireframes of the five screens that carry the product.

### 1. New project with live suggestions (`/w/demo/p/new`)

```
┌ Foresight ─ Demo Team ▾ ──────────────────────────────────────── Ada ▾ ┐
│ Projects  Members  Dashboard  Me                                        │
├─────────────────────────────────┬───────────────────────────────────────┤
│ New project                     │ Suggested risks from 3 similar past   │
│                                 │ projects                              │
│ Title                           │                                       │
│ [Vendor API integration       ] │ ● Vendor API not ready by integration │
│                                 │   start                               │
│ Description                     │   materialized 3 of 4 · predicted 41% │
│ [Connect billing to Stripe    ] │   from: Payments v2, CRM sync,        │
│ [replacement vendor ...       ] │   Warehouse API  ⚠ surprise last time │
│                                 │                                       │
│ Tags  [vendor ×] [external ×]   │ ● Rate limits hit during load test    │
│       [+ add]                   │   materialized 1 of 2 · predicted 65% │
│                                 │                                       │
│ Planned  [2026-10-01]→[2026-12-15]│ ● Contract signature slips          │
│                                 │   materialized 2 of 3 · predicted 20% │
│          [ Create project ]     │                                       │
└─────────────────────────────────┴───────────────────────────────────────┘
```

### 2. Session page, `collect` phase (`/w/demo/p/{id}/session`)

```
┌ Vendor API integration · Pre-mortem ────────────────────── phase ●collect ○merge ○vote ○sealed ┐
│ "Imagine it is December 15th and this project has failed. Why?"                                │
│                                                                                                │
│ Your risks (private until the facilitator advances)                                            │
│  1. Stripe sandbox differs from production behaviour                                 [edit][×] │
│  2. Finance not available for UAT in November                                        [edit][×] │
│                                                                                                │
│  [ The vendor changes pricing mid-project______________________________ ] [ Add risk ]         │
│                                                                                                │
│ Facilitator panel (Ada only)                                                                   │
│  Submissions: Ada 2 · Grace 4 · Linus 0        Participants [+]        [ Advance to merge → ]  │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3. Session page, `vote` phase (same URL, everyone sees canonical risks, nobody sees votes)

```
┌ Vendor API integration · Pre-mortem ────────────────────── phase ●collect ●merge ●vote ○sealed ┐
│ Rate each risk. Your answers are hidden until the session is sealed.        Saved 4 of 6 ✓    │
│                                                                                                │
│ Risk                                              Probability it happens        Impact         │
│ Vendor API not ready by integration start         [====●======] 45%            ○○●○○ 3        │
│ Stripe sandbox differs from production            [=======●===] 70%            ○○○●○ 4        │
│ Finance unavailable for UAT                       [==●========] 25%            ○●○○○ 2        │
│ Vendor changes pricing mid-project                [●==========]  5%            ○○○○● 5        │
│ Rate limits during load test                      [     ·     ] —              —              │
│ Contract signature slips                          [     ·     ] —              —              │
│                                                                                                │
│ Facilitator: 2 of 3 voters complete                                    [ Seal session ]        │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4. Close-out grading (`/w/demo/p/{id}/closeout`)

```
┌ Vendor API integration · Close-out ───────────────────────────────── project: closed ┐
│ Grade each risk against what actually happened.                    Graded 5 of 6      │
│                                                                                        │
│ Risk                                   Team predicted   Outcome            Note        │
│ Vendor API not ready                   45% · agree 0.71  (●yes ○no ○partial) [slipped 3w]│
│ Stripe sandbox differs                 70% · agree 0.55  (○yes ●no ○partial) [        ] │
│ Finance unavailable for UAT            25% · agree 0.80  (○yes ○no ●partial) [1 of 2 wks]│
│ Vendor pricing change                   5% · agree 0.92  (○yes ●no ○partial) [        ] │
│ Rate limits during load test           60% · agree 0.40  (○yes ○no ○partial) [        ] │
│                                                                                        │
│ Surprises: things that happened that nobody predicted                                  │
│  • Legal blocked data-residency clause for 3 weeks        tags [legal] [external]  [×] │
│  [ Add a surprise ______________________________________ ]  ⓘ similar to "Contract slips"? │
│                                                                    [ Save gradings ]   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 5. Workspace dashboard (`/w/demo/dashboard`)

```
┌ Demo Team · Calibration ─────────────────────────────────────────────────────────────┐
│ ┌ Brier ─────┐ ┌ Skill vs base ┐ ┌ Bias ──────────────┐ ┌ Confidence ────────────┐    │
│ │ 0.184      │ │ +0.21         │ │ +0.07 over-estimates│ │ +0.11 overconfident    │    │
│ │ 96 graded  │ │ base rate 0.38│ │ risk               │ │                        │    │
│ └────────────┘ └───────────────┘ └────────────────────┘ └────────────────────────┘    │
│                                                                                       │
│ Reliability diagram                        Brier trend (rolling 30)                   │
│ 1.0┤                       ●              0.30┤●                                      │
│    │                   ●  ╱               0.25┤  ╲●                                   │
│ obs│              ●  ╱                    0.20┤     ╲___●                             │
│    │         ●    ╱                       0.15┤          ╲__●   improving             │
│    │    ●  ╱  (dot size = n)                  └──────────────────────                 │
│ 0.0┤●╱                                          Checkout  DWH  Mobile  SSO            │
│    └──────────────── predicted 1.0                                                    │
│                                                                                       │
│ Blind spots (happened, predicted < 30%)     Chronic by tag                            │
│  • "Data migration needs rollback"  12%→yes   external  ████████░░ under by 0.18      │
│  • "Key engineer on leave"          18%→yes   timeline  ██████░░░░ under by 0.11      │
│  • "SSO vendor SAML quirks"         22%→yes   tech      ████░░░░░░ over  by 0.09      │
│                                                                                       │
│ Surprise rate: 1.5 per project · 28% of what went wrong was unpredicted               │
│ Members (admin): Ada 0.12 (calibrated) · Grace 0.27 (overconfident) · Linus 0.21 (under)│
└───────────────────────────────────────────────────────────────────────────────────────┘
```

### First-run walkthrough (after `docker compose up` and seed)

1. Open `http://localhost:3000`, log in as `ada@demo.local` / `demo1234`.
2. Land on `/w/demo`: four closed projects, one active project "Q4 Platform Hardening" whose session is in `collect`.
3. Open Dashboard: all tiles and charts populated from the four graded projects. Open Me: Ada's personal curve. Log in as Grace in another browser: her curve bends below the diagonal (overconfident).
4. Create a project tagged `vendor`: the suggestion panel appears immediately with provenance from past projects.
5. Both browsers open the active project's session: each submits risks and cannot see the other's. Ada advances to merge, marks a duplicate, adopts one suggestion, advances to vote. Both vote; neither sees the other's numbers. Ada seals: aggregates appear for both.
6. Ada closes the project, grades, adds a surprise. Dashboard tiles update on refresh.

## Architecture

| Decision | Choice |
|---|---|
| Services | `apps/web` (Next.js 15 App Router, TS), `services/auth` (FastAPI), `services/api` (FastAPI), `postgres` (16) |
| DB isolation | One Postgres instance, two databases + two roles (`foresight_auth`, `foresight_api`) plus `_test` twins, created by an init script. API never touches auth tables. |
| Auth tokens | Access JWT RS256, 15 min, claims `sub,email,name,iat,exp,iss=foresight-auth,aud=foresight-api,jti`, header `kid`. Refresh token: 32 random bytes, sha256 stored, 30 days, rotating families with reuse detection, delivered as httpOnly cookie `Path=/auth`. |
| API token verification | PyJWT + in-process JWKS cache (TTL 10 min, refetch on unknown `kid` at most every 30 s). On each request upsert `users` mirror (`id=sub,email,name,last_seen_at`). |
| Web token handling | Access token in memory; `AuthProvider` silently refreshes on mount; `apiFetch` does 401 → refresh (deduped) → retry once. Non-httpOnly hint cookie `fs_session=1` lets `middleware.ts` redirect unauthenticated navigations. All data pages are client components using TanStack Query. |
| CORS | auth: `allow_origins=[WEB_ORIGIN]`, credentials on. api: same origin, credentials off. |
| Python tooling | `uv` per service (pin `>=3.12,<3.13`; host has 3.14, `uv python install 3.12`), ruff, mypy strict, pytest-asyncio, httpx ASGITransport. |
| Web tooling | Tailwind v4 + shadcn/ui, react-hook-form + zod, TanStack Query, Recharts (follow `dataviz` skill for charts), vitest + testing-library + msw, Playwright for 3 smoke flows. |
| Migrations | Alembic; compose runs `auth-migrate` and `api-migrate` one-shot services before the apps. |
| Keys | `AUTH_JWT_PRIVATE_KEY_PEM` env, else file `infra/keys/dev_private.pem` (auto-generated in dev). `kid` = sha256(public DER)[:16]. |

## Repo layout

```
app_5k_c/
├── .env.example  .gitattributes (*.sh eol=lf)  .editorconfig  .gitignore  README.md
├── docker-compose.yml  docker-compose.override.yml (dev bind mounts + reload)
├── package.json            # root scripts: dev:db, dev:auth, dev:api, dev:web, test, e2e
├── docs/superpowers/specs/2026-09-25-foresight-design.md   # this design, committed as the spec
├── infra/postgres/init/01-create-databases.sh   infra/keys/.gitkeep
├── scripts/gen-keys.py  scripts/seed.py
├── services/auth/   pyproject.toml uv.lock Dockerfile alembic.ini alembic/  app/  tests/
│   app/: main.py  core/{config,keys,security,errors}.py  db/{base,session}.py
│         models/{user,refresh_token}.py  schemas/auth.py  routers/{auth,jwks,health}.py
│         services/{users,tokens}.py  deps.py
├── services/api/    pyproject.toml uv.lock Dockerfile alembic.ini alembic/  app/  tests/
│   app/: main.py  core/{config,security,errors,pagination}.py  db/{base,session}.py
│         models/{user,workspace,project,session,risk,vote,grading}.py
│         schemas/{common,workspace,project,session,risk,vote,grading,calibration,suggestion}.py
│         routers/{health,me,workspaces,projects,sessions,risks,votes,grading,calibration,suggestions}.py
│         services/{users,workspaces,projects,sessions,risks,votes,grading,calibration,suggestions}.py
│         deps.py (CurrentUser, require_member/admin/facilitator/participant)
└── apps/web/        next.config.ts  middleware.ts  components.json  vitest.config.ts  playwright.config.ts  Dockerfile
    app/: layout.tsx page.tsx (auth)/{login,register}/page.tsx
          (app)/layout.tsx (AuthGuard+AppShell)
          (app)/w/page.tsx  (app)/w/[workspaceId]/{layout,page}.tsx
          (app)/w/[workspaceId]/members/page.tsx  dashboard/page.tsx  me/page.tsx
          (app)/w/[workspaceId]/p/new/page.tsx  p/[projectId]/page.tsx (project + report)
          (app)/w/[workspaceId]/p/[projectId]/session/page.tsx (phase-driven UI)
          (app)/w/[workspaceId]/p/[projectId]/closeout/page.tsx (grading + surprises)
    components/: ui/ shell/ auth/ workspace/ project/ session/ grading/ charts/
    lib/: api.ts auth.ts auth-context.tsx env.ts schemas.ts utils.ts queries/*.ts
    __tests__/  e2e/
```

## Data model (API database)

Enums: `workspace_role(owner,admin,member)`, `project_status(planning,active,closed)`, `session_phase(collect,merge,vote,sealed)`, `risk_origin(participant,suggestion,surprise)`, `grading_outcome(yes,no,partial)`. UUID PKs, `created_at/updated_at` everywhere. Extensions: `pg_trgm`, `citext`.

- `users` (mirror): `id`(=JWT sub), `email citext unique`, `name`, `last_seen_at`.
- `workspaces`: `name`, `slug citext unique`, `created_by`.
- `workspace_members`: PK `(workspace_id,user_id)`, `role`. Members are added by email of an already-registered user (no invite table in MVP; 404 with a clear message otherwise).
- `projects`: `workspace_id`, `title`, `description`, `tags text[]`, `planned_start/end date`, `status`, `activated_at`, `closed_at`, `closed_by`, `archived_at`, `created_by`, `search_text` (STORED generated `title||' '||description`). Indexes: `(workspace_id,status,created_at desc)`, GIN on `tags`, GIN trgm on `search_text`. CHECK `(status='closed') = (closed_at is not null)`.
- `premortem_sessions`: `project_id unique`, `workspace_id` (denormalized), `created_by`, `facilitator_id` (mutable), `phase`, `phase_changed_at`, `sealed_at`, `fully_graded_at`.
- `session_participants`: PK `(session_id,user_id)`, `added_by`. Facilitator auto-added.
- `risks`: `project_id`, `session_id` (NULL only for surprises), `workspace_id`, `author_id`, `origin`, `statement`, `submitted_statement` (immutable original), `tags text[]`, `duplicate_of` (self FK, SET NULL), `source_risk_id` (for adopted suggestions), frozen aggregates `agg_vote_count, agg_mean_probability, agg_median_probability, agg_probability_stddev, agg_mean_impact, agg_risk_score` (NULL until seal). Partial index on canonical risks; GIN on tags; GIN trgm on statement.
- `votes`: `risk_id`, `session_id`, `workspace_id`, `user_id`, `probability smallint 0..100`, `impact smallint 1..5`, UNIQUE `(risk_id,user_id)`.
- `gradings`: `risk_id unique`, `project_id`, `graded_by`, `outcome`, `note`. Only canonical risks may be graded. Surprises are `risks` rows with `origin='surprise'` and an auto-created `yes` grading (so they flow into suggestions and surprise-rate without UNIONs).
- View `graded_predictions`: one row per (vote × canonical risk × grading × non-archived project) with `p = probability/100`, `o ∈ {0,0.5,1}`, `tags = risk tags else project tags`, `closed_at`. **All calibration queries read this view.**

Auth database: `users(id, email citext unique, name, password_hash, is_active, timestamps)`, `refresh_tokens(id, user_id, token_hash unique, family_id, expires_at, revoked_at, replaced_by_id, user_agent, created_at)`.

## State machines

Actors: admin+ = owner/admin; facilitator = `facilitator_id` or admin+; participant = row in `session_participants`; project editor = creator or admin+.

Project: `planning → active` (editor); `active → closed` (facilitator; requires session sealed if one exists; response warns `ungraded_count`). Closed is terminal; grading and surprises stay editable after close. Archive/unarchive (admin+) is orthogonal and hides from lists, suggestions and calibration. Delete (admin+) refused with 409 once a sealed session exists.

Session (forward only, `UPDATE ... WHERE phase=:from`, 409 on zero rows):
- create → `collect`: any member, project not closed/archived, no existing session.
- `collect → merge`: facilitator, ≥1 risk.
- `merge → vote`: facilitator, ≥1 canonical risk; risks frozen.
- `vote → sealed`: facilitator, ≥1 vote; computes `agg_*` for every canonical risk in the same transaction (`SELECT ... FOR UPDATE`); returns `incomplete_voters`.
- Delete session: facilitator, only in collect/merge. Participants add/remove: facilitator, before seal; removal refused if they have votes.

Visibility matrix:

| Action | collect | merge | vote | sealed |
|---|---|---|---|---|
| Submit / edit own risk | participant | – | – | – |
| Edit any / tag / mark duplicate / adopt suggestion | – | facilitator | – | – |
| Upsert votes | – | – | participant | – |
| See others' risks | facilitator: counts only | facilitator: all + author | all participants: canonical, no author | all members: canonical + aggregates + merged_from |
| See votes | – | – | own only | aggregates only; own vote to self |

Grading: facilitator, session sealed, project active/closed. Surprises: facilitator, project active/closed.

## Scoring (services/api/app/services/calibration.py — pure functions, unit-tested first)

Constants: `MIN_SCORE_N=10`, `MIN_BIN_N=5`, `MIN_TAG_N=10`, `BIN_COUNT=10`, `ROLLING_N=30`, `TREND_MIN_PTS=4`, `TREND_EPS=0.005`, `CALIBRATED_EPS=0.05`, `BLIND_SPOT_MAX_P=0.30`.

- `partial` = 0.5 everywhere. Votes on duplicates are impossible by the state machine and filtered by the view anyway. Surprises have no votes and never enter Brier.
- **Brier** `BS = mean((p−o)²)`; null if `N < MIN_SCORE_N`, response always carries `sample:{n, needed, sufficient}`. **Skill** `BSS = 1 − BS/BS_ref`, `BS_ref` uses workspace base rate `mean(o)`; null if `BS_ref=0`.
- **Bins**: `bin = min(probability // 10, 9)`; always return 10 bins with `n, mean_predicted, observed, reliable(n ≥ MIN_BIN_N)`; unreliable bins have `observed:null`.
- **Bias** `mean(p) − mean(o)` → `over_estimates_risk / under_estimates_risk / calibrated` (±0.05). **ECE** = weighted |gap| over reliable bins. **Overconfidence** = weighted `(mean_p_b − obs_b)·sign(mean_p_b − 0.5)` → `overconfident / underconfident / calibrated`.
- **Trend**: one point per closed project (ordered by `closed_at`): `brier_project`, `brier_rolling` (last 30 predictions, null under MIN_SCORE_N), `brier_cumulative`; direction by OLS slope of `brier_rolling` (`improving/worsening/flat/insufficient_data`).
- **Seal aggregates**: mean, median, population stddev, mean impact, `risk_score = mean_p/100 × mean_impact`, `agreement = clamp(1 − stddev/50, 0, 1)`.
- **Workspace extras**: blind spots (`o ≥ 0.5` and `mean_p < 0.30`, sorted by `o − mean_p`), false alarms (`o = 0`, `mean_p ≥ 0.70`), per-tag stats (tags with `n ≥ MIN_TAG_N`, `chronic under/over` at |bias| > 0.10), surprise rate (`surprises / closed graded projects`) and surprise share (`surprises / (surprises + materialized canonical risks)`).
- Worked example for the unit test: probabilities 80/30/60/90/20 with outcomes yes/no/partial/no/yes → BS = 0.318, bias = +0.06, overconfidence = +0.26.

## Suggestions (services/api/app/services/suggestions.py)

Input: workspace, title, description, tags, optional `exclude_project_id`, `limit` (10, max 25). Weights `W_TAG=0.6, W_TEXT=0.4, MIN_PROJECT_SIM=0.15, MAX_SOURCE_PROJECTS=20, ALPHA=0.2, CLUSTER_SIM=0.55`.
1. SQL: closed, non-archived projects in workspace with ≥1 grading, prefiltered by `tags && :tags OR search_text % :q`; `sim = 0.6·jaccard(tags) + 0.4·similarity(search_text, q)`; keep `sim ≥ 0.15`, top 20.
2. SQL: canonical graded risks of those projects (surprises included automatically) with `o`, `agg_mean_probability`, `agg_vote_count`.
3. Python: sort by `sim·(ALPHA + (1−ALPHA)·o)`, greedy cluster by trigram similarity ≥ 0.55 on normalized statements (one member per project per cluster), cluster `score = Σ sim·(ALPHA+(1−ALPHA)·o)`, `materialization_rate`, `occurrences`, `mean_predicted_probability`, top-3 tags, `sources[]` with provenance (project title, similarity, outcome, origin). Return top `limit`. Empty input or no matches → `suggestions: []`, `matched_projects: 0`.

## REST API (prefix `/v1`, Bearer auth, errors `{error:{code,message,details}}`, cursor pagination)

- **Me**: `GET /me` → `{user, workspaces[]}`.
- **Workspaces**: `POST /workspaces`, `GET /workspaces`, `GET|PATCH /workspaces/{ws}`, `GET /workspaces/{ws}/members`, `POST /workspaces/{ws}/members {email, role}` (admin+; user must exist), `PUT|DELETE /workspaces/{ws}/members/{user_id}` (last-owner guard; reassigns facilitator of unsealed sessions), `GET /workspaces/{ws}/tags`.
- **Projects**: `POST|GET /workspaces/{ws}/projects` (`?status&tag&q&include_archived`), `GET|PATCH|DELETE /projects/{id}`, `POST /projects/{id}/transition {to}`, `POST /projects/{id}/archive|unarchive`, `GET /projects/{id}/suggestions`, `POST /workspaces/{ws}/suggestions` (for the create form).
- **Sessions**: `POST /projects/{id}/session {participant_ids?}`, `GET|PATCH|DELETE /sessions/{id}`, `POST /sessions/{id}/transition {to}`, `POST /sessions/{id}/participants {user_ids}`, `DELETE /sessions/{id}/participants/{user_id}`.
- **Risks**: `GET|POST /sessions/{id}/risks`, `PATCH|DELETE /risks/{id}` (phase/role rules above; `duplicate_of` flattened to root, cycles rejected), `POST /sessions/{id}/risks/adopt {source_risk_id, statement?, tags?}`.
- **Votes**: `GET /sessions/{id}/votes/me`, `PUT /sessions/{id}/votes {votes:[{risk_id,probability,impact}]}` (bulk upsert, partial allowed), `GET /sessions/{id}/results` (sealed; aggregates + 10-bucket histogram per risk, no per-user attribution).
- **Close-out**: `GET /projects/{id}/closeout` (includes `possible_duplicates` for surprises via trgm > 0.5), `PUT /projects/{id}/gradings {gradings:[{risk_id,outcome,note?}]}`, `DELETE /gradings/{risk_id}`, `POST /projects/{id}/surprises {statement, tags?}`.
- **Calibration**: `GET /workspaces/{ws}/calibration/me`, `GET /workspaces/{ws}/calibration/users/{user_id}` (self or admin+), `GET /workspaces/{ws}/calibration` (`members[]` only for admin+), `GET /projects/{id}/report`.

Response shapes `UserCalibration`, `WorkspaceCalibration`, `ProjectReport` as designed: sample, brier, brier_skill, base_rate, bias(+label), ece, overconfidence(+label), bins[10], trend{direction, slope, points[]}, worst_calls[5]; workspace adds blind_spots, false_alarms, tags[], surprises{}, members[]; project report adds summary (expected vs actual materialized), per-risk miss, biggest_misses[3].

Tenant isolation: object-by-id routes load the row, check membership on its `workspace_id`, return 404 on non-membership. Individual votes are never exposed to other users. Per-user calibration is self-or-admin only.

## Auth service endpoints

`POST /auth/register {email,name,password}` → 201 `{access_token,user}` + refresh cookie; `POST /auth/login`; `POST /auth/refresh` (cookie; rotation; reuse → revoke family → 401); `POST /auth/logout` (revoke family, clear cookie); `GET /auth/me`; `GET /.well-known/jwks.json` (`Cache-Control: max-age=300`); `GET /health`. Login is constant-time (verify against dummy hash when user missing).

## Frontend pages

- `/login`, `/register` (forms, redirect to `?next`).
- `/w`: workspace list + create.
- `/w/[ws]`: overview: projects by status, "needs grading" list, calibration stat tiles.
- `/w/[ws]/members`: table, add by email, role change (admin+).
- `/w/[ws]/p/new`: create form with a live **Suggested risks** panel (debounced `POST /suggestions`) showing materialization rate and "nobody predicted this last time" badges for surprise-origin sources.
- `/w/[ws]/p/[id]`: project header, status transitions, session card, post-close report (expected vs actual, biggest misses).
- `/w/[ws]/p/[id]/session`: one page, phase-driven: collect (my risks + submit; facilitator sees submission counts), merge (facilitator table: edit, tag, mark duplicate, adopt suggestions, advance), vote (slider 0–100 + impact 1–5 per risk, autosave via bulk PUT, progress), sealed (results table with aggregate, agreement, histogram, my vote).
- `/w/[ws]/p/[id]/closeout`: grading table (yes/no/partial + note) with save, surprises list + add (with possible-duplicate nudge).
- `/w/[ws]/dashboard`: workspace calibration: reliability diagram (Recharts, diagonal reference, dot size = n), Brier trend line, bias/overconfidence tiles, blind spots, false alarms, per-tag bar chart, surprise rate, members table (admin+).
- `/w/[ws]/me`: personal calibration: same core charts + worst calls.

## Docker Compose

Services: `postgres` (healthcheck, named volume `pgdata`, init script creates roles/DBs), `auth-migrate`, `auth` (:8001, mounts `./infra/keys:/keys`), `api-migrate`, `api` (:8000, depends on auth healthy), `web` (:3000, standalone build, `NEXT_PUBLIC_*` build args). Override file adds bind mounts, `--reload`, `next dev`, anonymous volumes for `node_modules` and `.next`, `UV_CACHE_DIR=/tmp/uv`. `.env.example` lists all variables (DB passwords, `AUTH_*`, `API_*`, `NEXT_PUBLIC_*`).

## Testing strategy

- **auth tests**: real endpoints via httpx ASGITransport against `foresight_auth_test` (alembic upgrade once per session, per-test SAVEPOINT rollback): register/login, refresh rotation, reuse detection revokes family, logout, jwks shape, /me.
- **api tests**: `tests/jwt_utils.py` signs test JWTs with a session-scoped RSA key; JWKS cache patched with a static key map (no HTTP); one `respx` test for TTL/unknown-kid refetch. Fixtures `user_a`, `user_b`, `auth_headers`. Test files per resource plus `test_calibration_math.py` (pure, no DB, includes the worked example) and `test_suggestions.py` (fixture projects, asserts clustering and provenance).
- **web**: vitest for `api.ts` (401→refresh→retry, dedupe, hard fail), `PredictionForm`-style vote form, `ReliabilityDiagram` (ResizeObserver stub). Playwright (`npm run e2e`, expects compose up): register→reload keeps session→logout; create workspace→project→session→collect→merge→vote→seal; grade→dashboard shows Brier tile.
- TDD per the superpowers `test-driven-development` skill for every service/module.

## Seed data (`scripts/seed.py`, idempotent, run via `docker compose run --rm api uv run python scripts/seed.py`)

Registers 3 users through the **auth HTTP API** (`ada@demo.local`, `grace@demo.local`, `linus@demo.local`, password `demo1234`), then writes the API DB: workspace `demo` (Ada owner), 4 closed projects with sealed, fully graded sessions spread over 6 months (~8 canonical risks each, tags from `scope, tech, people, external, timeline, vendor`), personas: Ada calibrated, Grace overconfident, Linus underconfident (`random.Random(42)`), 1–2 surprises per project, plus one active project with a session in `collect`. Prints credentials.

## Build sequence (each step ends with tests green; the spec is committed first)

0. Write `docs/superpowers/specs/2026-09-25-foresight-design.md` from this plan; `git init`, `.gitattributes`, `.gitignore`, `.editorconfig`, `README.md`; commit.
1. Infra: `.env.example`, compose with `postgres` + init script, `scripts/gen-keys.py`. Verify: `docker compose up -d postgres`; `psql -l` shows 4 DBs.
2. Auth service: uv project, config, keys, models, migration 0001, security, tokens service, routers, tests. Verify: pytest green; curl register→refresh→me round-trip.
3. API skeleton: uv project, config, db, JWKS verification, users mirror, `/me`, `test_auth_verification.py`. Add `auth-migrate`/`api-migrate`/`auth`/`api` to compose. Verify: `docker compose up` → all healthy; `/v1/me` with a real auth token.
4. API: workspaces + members + tags (migration 0001 covers full schema incl. view) + tests.
5. API: projects (CRUD, transitions, archive) + tests.
6. API: sessions, participants, risks (collect/merge rules, duplicates, adopt), votes, seal aggregation + tests.
7. API: close-out gradings + surprises + project report + tests.
8. API: calibration pure functions (TDD with worked example) → view queries → endpoints + tests.
9. API: suggestions (SQL + clustering) + tests.
10. Web shell: Next scaffold, Tailwind/shadcn, `lib/auth.ts`, `lib/api.ts`, `AuthProvider`, middleware, login/register, vitest for api client.
11. Web: workspaces list/create, members, project list/create (with suggestions panel), project page + transitions.
12. Web: session page (all four phases), close-out page.
13. Web: dashboards (`/dashboard`, `/me`, project report) with Recharts per `dataviz` skill.
14. `scripts/seed.py`; verify dashboards populate from a clean volume.
15. Web Dockerfile (standalone), Playwright 3 flows, README quick-start. Final: `docker compose down -v && docker compose up --build` → seed → walk all flows.

## Verification (end-to-end)

1. `docker compose down -v; docker compose up --build -d` → `docker compose ps` shows postgres/auth/api/web healthy, both migrate services exited 0.
2. `uv run pytest` in `services/auth` and `services/api`: all green. `npm test` in `apps/web`: green.
3. Run seed; log in as `ada@demo.local`; `/w/demo/dashboard` shows Brier, reliability diagram with reliable bins, trend with 4 points, blind spots, tag chart; `/w/demo/me` differs per persona (Grace overconfident, Linus underconfident).
4. Create a project "Vendor API integration" tagged `vendor,external` → suggestions panel lists past vendor risks with materialization rates and a surprise badge.
5. Full manual flow as two users in two browsers: collect (cannot see each other's risks) → merge → vote (cannot see each other's votes) → seal (aggregates visible) → close project → grade → dashboards update live.
6. `npm run e2e` passes the 3 Playwright flows.

## Conversation log (Claude's replies, in order)

1. **Opening.** Classified the request as architectural (a new project), loaded the brainstorming skill, confirmed the working directory was empty, and ran four parallel web searches on candidate niches.
2. **Read-back and idea pitch.** Restated the brief (novel app, Next.js + Python + Postgres, three separate services, novelty over sales), listed the assumptions (small-team web app, complete MVP, local Docker), summarised the market check (pre-mortems are only templates, assumption tracking is only RAID rows, onboarding confusion capture is only surveys), and offered four ideas with Foresight recommended. User chose Foresight.
3. **Architecture questions.** Asked three independent questions: auth approach (custom FastAPI recommended), suggestion engine (deterministic recommended), and scope (complete MVP recommended). User accepted all three recommendations.
4. **Design delegation.** Launched two planning agents in parallel: one for the domain model, state machines, scoring math, suggestion algorithm and REST surface; one for service architecture, auth flow, repo layout, Compose, tooling and testing. Unified the two into this plan, keeping the domain agent's model (risks, votes, gradings, four session phases) and trimming invites and phase-event logging from the MVP.
5. **First submission.** Summarised Foresight and its three-service architecture, and flagged two environment concerns: the repo lives inside a OneDrive-synced folder, and the host has Python 3.14 with no `uv`. User replied that the plan is accepted only if the functionality cannot be done with a general-purpose chatbot.
6. **Chatbot check.** Added the feature-by-feature acceptance table: only generic risk brainstorming overlaps with a chatbot, and Foresight excludes it on purpose; every in-scope feature depends on multi-user hidden state, outcomes recorded later, or the organisation's own history. User asked to add a preview.
7. **Preview.** Added wireframes of the five core screens and a first-run walkthrough. User asked to add "the text".
8. **Research text.** Added the research and rationale section (brief, candidates, sources, decision log). User repeated the request; Claude asked which text was meant; user chose "Claude's chat replies", which this log records.

## Known risks

- **Repo lives inside OneDrive.** `node_modules`, `.venv`, `.next` and uv caches inside a synced folder cause file locks and slow watchers. Mitigation in the build: add those folders to `.gitignore`, and recommend in the README that the user either moves the repo out of OneDrive or excludes those folders from sync. Postgres data stays in a named Docker volume, never a bind mount. Dev runs Python and Next natively with only Postgres in Docker; full compose is for integration.
- **Host Python is 3.14 and `uv` is not installed**: install `uv` (`winget install astral-sh.uv`) and let it provision 3.12.
- **CRLF in shell scripts** breaks the Postgres init script: `.gitattributes` forces LF; verify with `git ls-files --eol`.
- **Port 5432** may be taken locally; fall back to `5433:5432`.
