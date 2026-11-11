Read AGENTS.md and docs/SPEC.md (the sections relevant to this stage).
Implement Django models, migrations, serializers, services, and permissions
for: accounts, host profiles, verification checks, categories, experiences
(+media), availability rules/exceptions, bookings (+events), payment
transactions, payouts (records only), conversations/messages, reviews, safety
reports, blocks, event collections, audit logs, saved hosts, notification
records. UUID PKs, integer minor units, UTC timestamps.
Build auth endpoints (register, login, logout, password reset, /users/me) and
read APIs for categories, experiences, hosts, collections with the filters,
sorting, and cursor pagination from the spec. Add the seed command.

Done when: migrations apply cleanly, API tests for auth, permissions, and
filters pass, OpenAPI docs are generated. Commit.
