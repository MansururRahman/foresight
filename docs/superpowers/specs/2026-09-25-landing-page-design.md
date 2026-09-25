# Landing Page & Design-Partner Applications — Design

Date: 2026-09-25
Status: Approved in brainstorming; pending written-spec review

## 1. Purpose

Foresight has no public face: `/` redirects anonymous visitors to `/login`. The founder is preparing to raise a pre-seed round and needs (a) a page to send outreach and social traffic to, (b) qualified leads to recruit 5–10 design-partner teams, and (c) a demand count to show investors.

**Success criteria**

- An anonymous visitor to `/` sees a landing page that explains the product and can apply as a design partner in under a minute.
- Applications are stored in the API database and can be exported as CSV.
- Logged-in users opening `/` still land in the app (`/w`).
- The channel that sent each applicant (`?ref=` / `utm_source`) is recorded.

**Assumptions** (from brainstorming, to be validated by customer interviews)

- Initial audience: delivery leads at software consultancies/agencies.
- The copy is a first draft and will change often, so it lives in one content file.

**Out of scope (YAGNI)**: admin UI for leads, email notifications, automated invites into workspaces, analytics tooling, production deployment (separate spec), a separate marketing site.

## 2. Page content & structure

Single server-rendered page at `/`, built with existing Tailwind v4 + shadcn/ui components. Sections, top to bottom:

1. **Header**: "Foresight" wordmark · "Log in" link (`/login`) · "Apply as design partner" button (anchor-scrolls to `#apply`).
2. **Hero**
   - Headline: "Your team saw it coming. Nobody wrote it down."
   - Subhead: "Foresight runs anonymous pre-mortems for project teams, then scores who predicted what, so your team's foresight gets measurably better with every project."
   - CTA button + "Free for design partners."
3. **Problem**: three cards: "Risks go unspoken in meetings" · "Risk registers are written once and never checked" · "Retros don't show whether you're getting better."
4. **How it works**: four steps: **Predict** privately → **Merge & vote** on probability and impact → **Seal** the forecast → **Grade** at close-out and see calibration. Includes a static screenshot `public/landing/calibration.png` of the seeded demo's calibration dashboard.
5. **What you get**: anonymous input so juniors speak up · calibration score per person and team · blind-spot detection by risk tag · risk suggestions from past projects.
6. **Design-partner offer**: "We're working with 10 delivery teams. You get free access and direct input on the roadmap. We ask that you run one real project through Foresight and join two 30-minute feedback calls."
7. **Application form** (`id="apply"`): name · work email · company · role · team size (`1-10` / `11-50` / `51-200` / `200+`) · "What went wrong on your last project that someone probably saw coming?" (optional). Success shows an inline thank-you: "Thanks, we'll reach out within 2 business days."
8. **Footer**: © Foresight · contact email · privacy note: "We only use this to contact you about the design partner programme."

All user-visible copy lives in `apps/web/content/landing.ts`. The contact email defaults to `hello@foresight.example` and must be replaced with a real address before launch.

## 3. Data model

New migration `services/api/alembic/versions/0003_leads.py` (hand-written, like 0001/0002).

Postgres enums, created in the migration and mapped with `pg_enum(..., create_type=False)`:

- `lead_team_size`: `1-10`, `11-50`, `51-200`, `200+`
- `lead_status`: `new`, `contacted`, `accepted`, `declined`

Table `leads`:

| Column | Type | Constraints |
|---|---|---|
| `id` | uuid | PK |
| `name` | text | not null, 1–120 chars (enforced in schema) |
| `email` | text | not null, stored lowercased/trimmed, unique |
| `company` | text | not null, 1–160 chars |
| `role` | text | not null, 1–120 chars |
| `team_size` | `lead_team_size` | not null |
| `story` | text | nullable, ≤2000 chars |
| `source` | text | nullable, ≤100 chars |
| `status` | `lead_status` | not null, default `new` |
| `created_at` | timestamptz | not null, default now() |
| `updated_at` | timestamptz | not null, default now(), updated on upsert |

No IP address or user agent is stored.

## 4. API

Files: `app/models/lead.py`, `app/schemas/lead.py`, `app/services/leads.py`, `app/routers/leads.py` (registered in `main.py`), `app/leads.py` (CLI). Follows the existing layering: the router is thin, the service holds the rules and commits.

### `POST /leads` (public, no auth)

Request body `LeadCreate`:

```json
{
  "name": "Ada Lovelace",
  "email": "ada@example.com",
  "company": "Analytical Ltd",
  "role": "Delivery lead",
  "team_size": "11-50",
  "story": "optional, ≤2000 chars",
  "source": "linkedin",
  "website": ""
}
```

- Strings are trimmed; required strings must be non-empty after trimming. `email` is validated with Pydantic `EmailStr` (adds the `email-validator` dependency) and lowercased. Empty `story`/`source` become `null`.
- `website` is a honeypot: if non-empty, respond 202 and store nothing.
- Existing email → update `name`, `company`, `role`, `team_size`, `story`, `source`, `updated_at` via `INSERT … ON CONFLICT (email) DO UPDATE`; `status` and `created_at` are preserved.
- Response: `202 {"status": "received"}` in every accepted case (new, repeat, honeypot), so responses never reveal whether an email already exists.
- Validation errors: 422 in the standard `{"error": {"code", "message", "details"}}` envelope (existing handler).
- Rate limit: max 5 requests per rolling 60 seconds per client IP (`request.client.host`), in-process memory, applied only to this route. Exceeding it raises `AppError(429, "rate_limited", ...)`. The limiter is a small injectable class so tests can reset it or give it a fake clock. The IP is never persisted. (Production must run uvicorn with proxy headers so the real client IP is used; that belongs to the deploy spec.)
- CORS: no change; the web origin is already allowed for `POST` with `Content-Type`.

### Export CLI

`python -m app.leads export [--status new|contacted|accepted|declined]` writes CSV to stdout with header `created_at,name,email,company,role,team_size,status,source,story`, ordered by `created_at` ascending. In Docker: `docker compose run --rm api python -m app.leads export > leads.csv`.

## 5. Web

Before writing web code, read `apps/web/AGENTS.md` and the relevant docs in `node_modules/next/dist/docs/` (Next.js 16 has breaking changes).

### Routing

- `apps/web/app/page.tsx` becomes a server component that renders the landing page (replaces the client-side redirect). It exports metadata: title "Foresight: pre-mortems that make your team better at predicting risk", description, and Open Graph title/description/image (`/landing/calibration.png`).
- `apps/web/proxy.ts`: add `/` to `config.matcher`; when `pathname === "/"` and the `fs_session` hint is present, redirect to `/w`. Otherwise fall through. A stale hint is handled as today (`/w` → 401 → `AuthProvider` → `/login`).

### Components

- `apps/web/content/landing.ts`: typed copy object for every section.
- `apps/web/components/landing/`: `LandingHeader`, `Hero`, `Problem`, `HowItWorks`, `Benefits`, `Offer`, `LeadForm`, `LandingFooter`. Only `LeadForm` is a client component.
- `LeadForm`:
  - zod schema mirroring the API rules; inline field errors on submit/blur.
  - Team size uses the existing `select` component; story uses `textarea`.
  - Hidden honeypot input named `website`: visually hidden, `tabIndex={-1}`, `autoComplete="off"`, `aria-hidden`.
  - Reads `ref` (preferred) or `utm_source` from the URL via `useSearchParams` into `source`, truncated to 100 chars. (Wrap in `<Suspense>` if Next 16 requires it for `useSearchParams` on a statically rendered page.)
  - Submit disabled while pending; on success replace the form with the thank-you message; on error show an inline message ("Something went wrong, please try again", or the rate-limit message for 429).
  - All inputs have associated labels; keyboard usable.
- `apps/web/lib/queries/leads.ts`: `useSubmitLead()` TanStack `useMutation` posting to `${NEXT_PUBLIC_API_URL}/leads`. It must not attach a bearer token or trigger the refresh/`fs:unauthorized` flow: add an `auth?: boolean` option (default `true`) to `ApiInit` in `lib/api.ts`; with `auth: false`, `apiFetch` sends no token and skips the 401 refresh/retry, while still using `readError` for the envelope. Cover the new option in `__tests__/api.test.ts`.
- `apps/web/public/landing/calibration.png`: captured from the seeded demo stack (Ada's calibration dashboard) with Playwright; commit the image.

## 6. Testing

**API (`services/api/tests/test_leads.py`)**
- valid submission → 202, row stored, email lowercased/trimmed, `status = new`
- works without an Authorization header
- repeat email → still one row, fields updated, `status` preserved (set to `contacted` first), `created_at` unchanged
- honeypot filled → 202, no row
- missing/invalid fields (bad email, empty name, unknown team size, story > 2000) → 422 envelope
- 6th request within 60 s from the same client → 429 `rate_limited`; limiter reset between tests
- export CLI: CSV header and rows in order; `--status` filters

**Web (vitest, `apps/web/__tests__/`)**
- `LeadForm.test.tsx`: validation messages; successful submit shows thank-you and sends the expected body; API error shows error message; `?ref=linkedin` ends up as `source`; honeypot not visible to users.
- `proxy.test.ts`: `/` with hint → redirect `/w`; `/` without hint → next.

**E2E (Playwright, `apps/web/e2e/landing.spec.ts`)**
- anonymous `/` shows the hero and submits an application successfully
- logged-in user visiting `/` lands on `/w`
- existing specs do not navigate to `/` directly (checked: `auth.spec.ts` asserts `/login` only after visiting `/w`), so no changes are expected; re-run the full e2e suite to confirm

**Quality gates**: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy app` (strict), `uv run pytest`; `npm run lint`, `npm run typecheck`, `npm test`.
