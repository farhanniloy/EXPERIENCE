Read AGENTS.md and docs/SPEC.md (the sections relevant to this stage).
Implement availability (weekly rules, exceptions, notice, advance window,
buffer, timezone) and the slot API. Implement instant booking and
request-then-approve booking with temporary holds, the exclusion constraint,
row locking, idempotency keys, strict state transitions, and Celery hold
expiry. Build the booking UI (slot picker, public-venue field, booking detail
pages, accept/decline/cancel/complete).

Done when: tests prove two concurrent overlapping requests cannot both
succeed, duplicate submissions create one booking, expired holds release
slots, and invalid transitions are rejected. Commit.
