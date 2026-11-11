# Along: Project Rules (always follow)

## Product
Along is a premium, adults-only, NON-SEXUAL marketplace where customers book
a host to accompany them to activities (movies, cafés, festivals, concerts,
photography, city exploration, museums, games, hobbies).
Tagline: "Good company. Great experiences."
Launch market: Bangladesh. Currency BDT, timezone Asia/Dhaka, English UI.
Country, currency, timezone, brand name, and theme live in central config,
never hardcoded. Keep UI strings centralized so Bangla can be added later.
User-facing term for providers: "host" (code may use `companion`).

## Stack (use latest stable; pin exact versions in lockfiles and docs/versions.md)
- Frontend: Next.js (App Router), TypeScript strict, Tailwind, Motion, Lucide.
- Backend: Python, Django, Django REST Framework, API under /api/v1/.
- DB: PostgreSQL (UUID PKs, migrations, FKs, indexes). No PostGIS for now; use a `city` field.
- Redis + Celery only for: emails, booking-hold expiry, reminders.
- Docker Compose for local dev. Config via environment variables; .env.example committed, no secrets.
- Modular monolith. No microservices, Kafka, or Kubernetes.

## Repo layout
along/{frontend, backend/{config,modules/*,infrastructure}, infrastructure, docs}
Backend modules: accounts, profiles, verification, experiences, categories,
discovery, availability, bookings, payments, messaging, reviews, events,
notifications, safety, administration. Business logic in service functions,
not views or serializers.

## Auth and security
- Django session auth with HTTP-only, Secure, SameSite cookies + CSRF.
- Next.js proxies /api to Django so the browser stays same-origin.
- No tokens in localStorage.
- Never trust the client for prices, availability, payment status, or permissions.
- Every endpoint checks permissions and object ownership server-side.
- Never expose ID documents, phone numbers, or exact addresses in any API response.
- Rate-limit auth, messaging, and booking endpoints.

## Booking rules (core of the product)
- Statuses: requested, awaiting_payment, confirmed, in_progress, completed,
  declined, cancelled, expired, disputed. Enforce allowed transitions in one place.
- Prevent overlap with a PostgreSQL exclusion constraint (btree_gist) on
  (host, time range) for active statuses, plus transactions and row locking.
- Idempotency keys on booking creation and payment initiation.
- Holds expire via Celery (default 15 min, configurable).
- Booking stores an immutable snapshot (title, duration, price, fee, tax,
  currency, cancellation rules, times). Later listing edits never change it.
- Money = integer minor units + currency code. Timestamps = UTC, tz-aware.

## Payments
- Provider-agnostic adapter interface (initiate, verify, webhook, refund).
- Include a sandbox/mock adapter, labeled in the UI and API, that refuses to
  load unless DEBUG/dev settings are on. It must never run in production.
- Payment is confirmed only by server-side provider verification or a
  signed webhook, never by a browser redirect.
- No custody/escrow logic. Track payouts and refunds as records only.
- Document what real credentials production needs. Never claim an
  integration works when it is only simulated.

## Safety and misuse prevention (required, not optional)
- Adults only (18+ confirmation and verification interface).
- Prohibited: sexual services or innuendo, suggestive imagery, body-focused
  or "date"-style pricing, off-platform contact sharing.
- Automatically flag listings, bios, and messages containing solicitation
  terms, phone numbers, or WhatsApp/Telegram/social links, and route them
  to a moderation queue.
- First listing from any host requires admin approval before going public.
- First bookings must use a public venue (enforce in the booking form).
- Block, report, and per-booking safety check-in available everywhere.
- Account suspension, incident records, and audit logs for admin actions.
- Public profiles show only general location (city/area).

## Design
Premium, editorial, restrained. Not a SaaS dashboard, not a dating app.
Palette: ivory #F7F5F0, white #FFFFFF, charcoal #20201F, stone #77736D,
burgundy #75404A (accent), olive #777B61, border #E8E4DC.
Type: Playfair Display for select headlines, Inter or Geist for UI,
Geist Mono for numbers only. Generous whitespace, consistent grid, small radii,
few shadows, no neon, no heavy gradients, no glassmorphism.
Motion: 150-350ms, purposeful, respect prefers-reduced-motion.
Images: local placeholder assets with alt text; remote sources only with a
local fallback. A missing image must never break the layout.
Every page needs loading, empty, and error states. No dead buttons.

## Code quality
- Strict TypeScript, no `any` without a comment. One typed API client; no scattered fetch calls.
- Small components, no giant files. Validate all input on the backend.
- Avoid N+1 queries (select_related/prefetch_related). Paginate lists.
- Seed demo data with a management command, labeled as sample data.
- Never silently swallow errors. Structured logging, Sentry-compatible.
- Mandatory tests: double-booking race test, state-machine tests,
  permission tests, payment idempotency and webhook tests.

## Workflow
- Work in stages. Finish one cleanly before starting the next.
- Run the app, tests, lint, and type-check yourself and fix failures.
- Commit after each stage with a clear message.
- Record assumptions in docs/decisions.md.
- Make sensible decisions; don't ask unnecessary questions.
- At the end of each stage, report: what was built, how to run it, tests run
  and results, known limitations.
- Detailed requirements live in docs/SPEC.md. Read the relevant section
  before each stage. AGENTS.md wins on any conflict.
- One account can hold both customer and host capabilities.
- Never use dating or romantic framing in names, copy, collections, or categories.

## Out of scope for MVP
PostGIS, payout/reconciliation workflows, multiple admin roles (use
staff vs superuser), Bangla translation, WebSockets, native apps.
