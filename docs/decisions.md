# Architecture decisions

## 1. Monorepo structure
The repository is organized into a Next.js frontend and a Django backend, matching the required product architecture. This keeps the app easy to understand while preserving a clear boundary between UI and server logic.

## 2. PostgreSQL-first configuration
The default runtime uses PostgreSQL because the product requirements call for time-based booking constraints and PostgreSQL-specific exclusions. A migration creates the btree_gist extension so the project is ready for overlap prevention rules without manual database setup.

## 3. Same-origin proxy for API calls
The frontend calls the backend via /api/* routes. Next.js rewrites those requests to the Django service, which maintains a same-origin browser experience and simplifies deployment.

## 4. Docker Compose for local development
The Compose stack includes PostgreSQL, Redis, the Django API, Celery, and the Next.js web app so developers can start the full environment with a single command.
