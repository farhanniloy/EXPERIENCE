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
4. API health check: http://localhost:8000/api/v1/health/

## Included defaults
- PostgreSQL with the btree_gist extension enabled via migration
- Redis and Celery service wiring
- Django health endpoint
- Next.js proxy route that forwards /api requests to Django
- Minimal test and lint validation commands
