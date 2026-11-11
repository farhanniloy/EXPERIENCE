Read AGENTS.md and docs/SPEC.md (the sections relevant to this stage).
Implement reporting, blocking, reviews tied to completed bookings (one per
booking, verified label, moderation), account suspension, incident records,
per-booking safety check-in, host application approval, experience
moderation, special event collections (admin-managed, auto-expire, shown on
the homepage when active), and the admin area. Use Django admin plus custom
pages where needed. Log sensitive admin actions in the audit log. Support
staff vs superuser permissions.

Done when: admin can approve hosts, moderate experiences, view bookings and
payments, and handle reports; blocking restricts interaction; audit entries
are written; sensitive verification data never appears in any public or
customer API response. Commit.
