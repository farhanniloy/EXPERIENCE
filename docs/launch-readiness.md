# Stage 8: hardening and QA

## What was built

- Production Django settings reject `DEBUG=True`, missing/development secrets,
  wildcard hosts, or missing host/CSRF-origin allowlists. HTTPS redirect,
  HSTS, secure cookies, content-type protection, and an explicit referrer
  policy are configured for production. HSTS subdomains and preload remain
  opt-in.
- Playwright browser journeys cover customer registration and empty states,
  host adult-confirmation and application forms, staff report moderation and
  non-staff denial, booking check-ins and reports, booking retry idempotency,
  responsive layouts, and reduced-motion behavior.
- Backend regression checks cover CSRF enforcement and login throttling; the
  suite also exercises permission boundaries, private-data filtering, payment
  webhook replay safety, state transitions, and booking concurrency.

## Folder structure

```text
along/
├── backend/
│   ├── config/                 # Django settings and URL configuration
│   └── modules/platform/       # Marketplace domain, API, and tests
├── frontend/
│   ├── app/                    # Next.js App Router pages
│   ├── components/             # UI and workflow components
│   ├── lib/                    # Typed API client and shared helpers
│   └── tests/e2e/              # Playwright browser journeys
├── infrastructure/             # Local infrastructure support
└── docs/                       # Product specification and runbooks
```

## Run locally

Requirements: Docker Desktop with Compose, Node.js 20.9 or newer, and npm.

```sh
cp .env.example .env
docker compose up --build
```

The app is available at `http://localhost:3000`; the Django API and admin are
at `http://localhost:8000`. Compose starts PostgreSQL and Redis and applies
database migrations when the backend starts.

Useful commands:

```sh
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend python manage.py check
docker compose exec backend python manage.py test modules.platform
docker compose exec backend python manage.py seed_sample_data
docker compose exec backend python manage.py createsuperuser
cd frontend
npm install
npx playwright install chromium
npm run lint
npx tsc --noEmit
npm run test:e2e
```

Playwright starts a separate Next.js dev server on port 3100 by default; it
does not reuse or change the Compose frontend on port 3000. Set
`PLAYWRIGHT_PORT` to use another local port.

## Database, admin, and demo data

PostgreSQL 16 runs as the `postgres` Compose service. The default local
database is `along`, with credentials supplied by `.env`; keep the example
values local-only and replace them for any shared environment. The Compose
backend migrates automatically; use `manage.py migrate` for explicit schema
updates.

Create a Django staff administrator interactively with
`docker compose exec backend python manage.py createsuperuser`. Use a unique
strong password and do not commit it. The custom staff workspace is
`http://localhost:3000/admin`; Django's built-in admin is
`http://localhost:8000/admin/`.

Seed public sample catalog data with `manage.py seed_sample_data`. Sample
accounts use `sample+<host-slug>@along.local` and are intentionally created
with unusable passwords. They are public listing fixtures, not sign-in demo
accounts. Create customer accounts through the signup UI or API. The
development-only adult confirmation is a self-attestation simulation and is
not identity verification.

## External integrations requiring real credentials

- **Payments:** a real provider adapter, merchant/API credentials, webhook
  signing secret, callback URLs, and verified refund behavior. The current
  sandbox simulates outcomes and never moves money.
- **Email:** production SMTP or transactional email credentials, a verified
  sending domain, and delivery/bounce configuration. Local email uses the
  console backend.
- **Age/identity verification:** a production verification vendor, credentials,
  callback configuration, and approved retention/privacy terms. The local
  development adapter records only self-confirmation.
- **Operations:** production TLS/domain and hosting configuration, and a
  Sentry-compatible DSN if error reporting is enabled.

## Tests and checks

The Playwright journeys stub API responses to keep browser tests isolated and
repeatable. Backend tests exercise the real Django API and database behavior.
Run both suites and the lint/type/migration commands above before release.
The production-oriented Django check is:

```sh
docker compose exec backend python manage.py check --deploy
```

For that check to pass, run Django with `APP_ENV=production`,
`DJANGO_DEBUG=False`, a unique secret, an explicit `DJANGO_ALLOWED_HOSTS`
allowlist, an explicit `DJANGO_CSRF_TRUSTED_ORIGINS`, and HTTPS/HSTS settings
appropriate to the deployed TLS terminator. Do not enable HSTS subdomains or
preload until all affected hosts have been verified over HTTPS. Do not apply
production settings to the development Compose stack.

Latest local verification:

- Playwright: **9 passed** (customer registration, host onboarding/dashboard,
  staff permissions and report handling, safety actions, completed-booking
  reviews, booking retry, sandbox payment outcomes, and responsive/error states).
- Backend platform suite: **40 passed**.
- Frontend ESLint, TypeScript `--noEmit`, and optimized Next.js build: passed.
- Django migration consistency and standard checks: passed; no model changes
  require migrations.
- Production `check --deploy`: no Django security warnings with explicit
  production-like values, including opt-in HSTS subdomains/preload; one
  non-blocking drf-spectacular enum-name collision warning remains.
- Compose configuration and local frontend/backend health checks: passed.
- Unsafe `APP_ENV=production` with `DJANGO_DEBUG=True` is rejected at startup.

## Known limitations

- Admin MFA is not implemented and is a launch blocker.
- The payment adapter and age-confirmation provider are development
  simulations; production credentials and integrations are not configured.
- The browser journeys mock API responses; they are UI workflow tests, not a
  substitute for the real-backend API and concurrency tests.
- Django's built-in throttles use the configured Django cache. Production
  multi-worker deployments need a shared, appropriately secured cache or an
  edge rate limiter; the local Compose setup is not a production rate-limit
  topology.
- Sample catalog accounts cannot sign in. Collection expiry cleanup runs on
  collection access rather than a scheduled task.
- Backup restoration, production load testing, and vendor/webhook acceptance
  tests require deployment infrastructure and credentials and were not
  performed locally.
- OpenAPI generation emits a non-blocking enum-name collision warning for
  multiple fields named `action`.

## Production checklist

- [ ] Deploy behind TLS and set `APP_ENV=production`, `DJANGO_DEBUG=False`,
      a unique `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and the required
      CSRF origins.
- [ ] Confirm the TLS proxy forwards scheme information only from trusted
      infrastructure; verify secure cookies, HTTPS redirect, and HSTS
      configuration before enabling preload.
- [ ] Add and enforce administrator MFA; restrict staff access and verify
      audit-log retention and access.
- [ ] Integrate and test the real payment provider, signed webhooks,
      idempotency, refunds, and failure handling. Ensure the sandbox cannot
      load in production.
- [ ] Integrate a real age/identity verification provider and production
      email delivery; configure secrets through the deployment secret store.
- [ ] Configure shared/edge rate limits, structured logs, alerting, and
      Sentry-compatible error reporting.
- [ ] Run dependency and image scans; review secret rotation, data retention,
      deletion, consent, privacy, and legal requirements.
- [ ] Take a production-equivalent backup and perform a restore test.
- [ ] Run full migration, permission, booking concurrency, webhook, and
      release smoke tests against a production-like PostgreSQL environment.
- [ ] Complete load testing for discovery, profiles, authentication,
      availability, and booking creation before launch.
