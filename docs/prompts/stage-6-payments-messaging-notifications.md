Read AGENTS.md and docs/SPEC.md (the sections relevant to this stage).
Implement the payment adapter interface, the dev-only sandbox adapter
(success, failure, expiry; labeled; refuses to load in production),
signed-webhook verification, idempotent payment handling, refund and payout
records, and the transactional outbox. Add booking-linked messaging with
membership-based authorization, read status, unread counts, rate limiting,
block enforcement, and content flagging. Add Celery email notifications for
the events in the spec.

Done when: webhook and idempotency tests pass, a browser redirect alone can
never confirm a booking, non-members cannot read conversations, the customer
journey (search -> book -> pay -> confirmation -> dashboard) works end to
end. Commit.
