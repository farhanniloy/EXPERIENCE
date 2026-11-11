# Along

A monorepo foundation for the Along marketplace MVP.

## Stack
- Frontend: Next.js (App Router)
- Backend: Django + DRF
- Database: PostgreSQL
- Cache / broker: Redis + Celery
- Local orchestration: Docker Compose

## Quick start

1. Copy the sample environment file if needed:
   cp .env.example .env
2. Start the stack:
   docker compose up --build
3. Visit http://localhost:3000 to view the frontend.
4. Visit http://localhost:8000 to open the API reference.
5. API health check: http://localhost:8000/api/v1/health/
6. Seed the database with sample marketplace records:
   docker compose exec backend python manage.py seed_sample_data
7. API reference: http://localhost:8000/api/docs/

Accounts can be created at `/signup`, hosts can apply at
`/become-a-companion`, and authenticated booking summaries are available at
`/dashboard` and `/dashboard/companion`. Staff moderation is available at
`/admin/moderation`. The age-confirmation simulation is development-only and
does not verify identity.

## Included defaults
- PostgreSQL with the btree_gist extension enabled via migration
- Redis and Celery service wiring
- Django health endpoint
- Next.js proxy route that forwards /api requests to Django
- Session-based API authentication and versioned public catalog endpoints
- OpenAPI schema at docs/api/openapi.yaml
- Backend tests: docker compose exec backend python manage.py test
- Frontend checks: cd frontend && npm run lint && npx tsc --noEmit
