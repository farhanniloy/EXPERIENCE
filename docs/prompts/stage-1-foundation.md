Read AGENTS.md and docs/SPEC.md (the sections relevant to this stage).
Inspect the repo first and reuse anything worthwhile.
Create the monorepo foundation: Next.js app, Django project with the module
folders, PostgreSQL (with btree_gist extension enabled via migration), Redis,
Celery, Docker Compose, .env.example, .gitignore, README, docs/decisions.md,
docs/versions.md. Add a /api/v1/health endpoint and a frontend page that calls
it through the proxy.

Done when: `docker compose up` starts everything, health check works end to
end, migrations run, lint and tests pass (even if minimal). Commit.
