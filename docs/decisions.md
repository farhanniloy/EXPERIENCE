# Architecture decisions

## 1. Monorepo structure
The repository is organized into a Next.js frontend and a Django backend, matching the required product architecture. This keeps the app easy to understand while preserving a clear boundary between UI and server logic.

## 2. PostgreSQL-first configuration
The default runtime uses PostgreSQL because the product requirements call for time-based booking constraints and PostgreSQL-specific exclusions. A migration creates the btree_gist extension so the project is ready for overlap prevention rules without manual database setup.

## 3. Same-origin proxy for API calls
The frontend calls the backend via /api/* routes. Next.js rewrites those requests to the Django service, which maintains a same-origin browser experience and simplifies deployment.

## 4. Docker Compose for local development
The Compose stack includes PostgreSQL, Redis, the Django API, Celery, and the Next.js web app so developers can start the full environment with a single command.

## 5. Stage 3 backend implementation
Stage 3 groups the domain models in the Django `platform` app while exposing
versioned, domain-specific API routes. This keeps initial migrations coherent
and lets later stages extract business modules without changing the public
API. Public API endpoints expose approved, published records only; sample
accounts are created with unusable passwords and labeled with `sample+` email
addresses. Password reset uses Django's configured email backend (console in
development). PostgreSQL booking overlap protection is installed by a
vendor-conditional migration so local SQLite checks remain usable.
Marketplace accounts keep UUIDs and link one-to-one to Django's existing auth
user. Domain ownership FKs point to the auth user, preserving the deployed
integer FK columns and existing admin migration history while keeping
marketplace account IDs UUID-based.

The launch brand, country, currency, and timezone use backend environment-backed
settings in `backend/config/product.py` and frontend public environment-backed
values in `frontend/lib/site-config.ts`. Generated OpenAPI is kept in
`docs/api/openapi.yaml`; regenerate it with
`cd backend && python manage.py spectacular --file ../docs/api/openapi.yaml --validate`.

## 6. Host onboarding and moderation
Host applications and listings are persisted in the platform API. The age
confirmation endpoint is a clearly labeled local development simulation and
is disabled when DEBUG is off or APP_ENV is production; it is not identity
verification. Profile and experience photos currently use validated HTTPS
URLs or local asset paths. Host applications and each host's first listing
require staff review. Prohibited solicitation terms and phone/social contact
details place profile or listing content in the staff moderation queue. Public
catalog pages merge approved database records with the existing sample
fixtures until fixture-backed sample content is retired.
Prices are stored and sent by the API in integer currency minor units. Host
forms accept normal currency values, and formatting and budget filters use the
currency's configured minor-unit scale.
