# Along: Technical Spec (condensed from PRD v1.0)

Precedence: AGENTS.md wins on any conflict with this file.
Priorities: P0 = needed for launch, P1 = later, P2 = advanced.

## 1. Core goal
A customer finds a verified host and completes a safe, reliable, paid booking.
Everything else supports that transaction. Non-sexual, adults only.

## 2. Roles
- One account can be both customer and host. Model as capabilities on one
  user, not separate account types.
- Customer: browse, search, book (instant or request), pay, message,
  cancel, review, report, block, save hosts.
- Host: apply, verify, build profile, publish experiences, set prices and
  availability, toggle instant booking, accept/decline, message, view
  earnings and payouts, report customers.
- Admin roles: for MVP use staff vs superuser. Design permissions so
  support / moderation / finance can be split later. Admin MFA required in production.

## 3. Localization and privacy
- Config-driven country, currency, timezone. Launch with Bangladesh by city
  (city launch flags), BDT, Asia/Dhaka. UI in English, strings centralized
  for Bangla later.
- ISO country and currency codes. UTC in DB. IANA timezone per user and per
  experience. Don't assume 2 decimal places for currencies.
- Public pages show city/area only. Never expose residential addresses,
  live location, phone, or ID data. `meeting_location_private` is visible
  only to the two booking parties.
- Meetings in public venues only for MVP; residential meetings prohibited.

## 4. Features (all P0 unless noted)
### Auth/accounts
Email registration + email verification, login/logout, password reset,
profile management, account deletion request, session management, login
rate limiting. Phone verification: P1 (build the endpoint shape, adapter only).
Age gate: users failing age verification cannot book. Store only
verification references and results, never raw ID documents.

### Host onboarding
Steps: account -> "Become a host" -> profile info -> age/identity
verification (dev adapter locally) -> intro text -> photos -> interests and
categories -> service locations -> submit -> admin review.
Application states: draft, submitted, under_review, approved, rejected, suspended.
Only approved hosts can publish experiences.

### Host profile
display name (not legal name), photos, headline, bio, city, languages,
interests, categories, verification badges, avg rating, completed bookings,
availability, published experiences.

### Experiences and categories
Fields: title, description, categories (many-to-many), images, duration,
min/max duration, pricing_type (fixed|hourly), price, service area, booking
mode, cancellation policy, status (draft|published|inactive).
Seed categories: Movies, Food and cafés, Photography, Festivals,
Concerts and entertainment, City exploration, Museums and culture,
Sports and games, Hobbies, Seasonal events.
Collections (basic P0): admin-curated, selected experiences, banner,
description, optional city/country restriction, active period, auto-expire.
They extend the catalog; they are NOT a separate event-booking system.
Collection names must stay non-romantic (no "Valentine's" or "date" themes).

### Search
Filters: category, text query, city, budget, date, duration, min rating,
language, instant-booking, verified host.
Sort: relevance, price asc, rating, recently active.
Pagination: cursor pagination. Results show host photo, name, city,
title, price, duration, rating, verification, availability indicator.
Never reveal exact locations. Search on PostgreSQL only for now.

### Availability
Weekly recurring rules, unavailable dates, extra available dates, buffer,
minimum notice, max advance window, timezone-aware. Slot API accounts for
confirmed bookings and active holds and never exposes other customers' data.

### Booking
Modes:
- Instant: select slot -> server validates -> hold slot -> pay -> confirmed
  -> notify both.
- Request: submit -> host notified -> accept/decline -> on accept status =
  awaiting_payment with a hold -> pay within window -> confirmed. Expired
  window releases the hold. Default window 15 min (configurable).
Statuses: requested, awaiting_payment, confirmed, in_progress, completed,
declined, cancelled, expired, disputed.
Allowed transitions:
- requested -> declined | awaiting_payment
- awaiting_payment -> confirmed | expired | cancelled
- confirmed -> cancelled | in_progress
- in_progress -> completed | disputed
Terminal states never go backward. Implement in one transition function.
"Accepted" is an event, not a stored status.
Booking snapshot (immutable): experience title, duration, start/end, host,
customer, base price, platform fee, tax, total, currency, cancellation
policy (JSONB), meeting arrangement.
The server calculates every price; never trust client totals or fees.

### Payments
Provider adapter interface; sandbox adapter in dev only; no escrow;
verify via signed webhooks or server-to-server verification.
Booking state and payment state are separate.
Payment states: pending -> failed | authorized -> captured -> refunded |
partially_refunded.
Payout states (records only for MVP): pending, eligible, processing, paid,
failed, reversed.
Webhooks: verify signature, validate reference, block replay, handle
duplicates, store events, flag discrepancies.
Use a transactional outbox for side effects (emails, notifications).
Reconciliation job: P1 (stub the task).

### Messaging
Booking-linked conversations, timestamps, read status, unread count,
report and block, rate limiting, basic content flagging. Membership check on
every request. Database-backed with polling; no WebSockets.

### Reviews
Only after completed bookings, one per customer per booking, rating 1-5,
optional comment, moderation status, verified-booking label, report action.
Private safety feedback is stored separately from public reviews.

### Safety
Prohibited: sexual services or solicitation, coercion, harassment, threats,
non-consensual recording, fake profiles, impersonation, exploitation,
trafficking, bypassing platform policies.
Build: reporting, blocking, suspension, moderator review queue, booking
incident records, emergency info page, cancellation/no-show policy.
Trusted-contact sharing: P1.
Reports must be actionable, not just stored.

### Notifications
Async email (Celery) for: verification, application status, booking
request/accept/decline, payment status, upcoming booking, cancellation,
refund, new message, review. SMS/push adapters are interfaces only.

### Admin
Overview, users, applications, verification status, experiences,
categories, collections, bookings, payments, payouts, refunds, reports,
moderation, audit logs. Analytics: P1. Log all sensitive actions.

## 5. Data model
Rules: UUID PKs, FKs, explicit constraints, migrations, tz-aware timestamps,
money = BIGINT minor units + CHAR(3) currency, JSONB only for snapshots/metadata.
Tables and key columns:
- users: email (unique, normalized), phone?, password_hash, display_name,
  birth_date (private), country_code, timezone, locale, status, timestamps
- companion_profiles: user FK, slug (unique), headline, biography, city,
  country_code, service_radius_km, status, instant_booking_enabled,
  average_rating, completed_bookings (cached aggregates)
- verification_checks: user FK, provider, provider_reference, type (age|identity),
  status, checked_at, expires_at. No raw documents.
- categories: parent?, slug (unique), name, description, cover image, icon,
  is_active, sort_order
- experiences: profile FK, title, slug, description, duration_minutes,
  min/max_duration_minutes, pricing_type, price_minor, currency,
  instant_booking_enabled, status
- experience_categories: (experience_id, category_id) composite PK
- experience_media: experience FK, object_key, media_type, sort_order
- availability_rules: profile FK, weekday, start_time, end_time, timezone, is_active
- availability_exceptions: profile FK, start_at, end_at, type (available|unavailable), notes
- bookings: customer FK, profile FK, experience FK, start_at, end_at,
  timezone, status, currency, base/fee/tax/total _minor, payment_deadline,
  meeting_location_private, cancellation_policy_snapshot (JSONB), idempotency key
- booking_events: booking FK, actor?, event_type, previous_state, new_state, metadata, created_at
- payment_transactions: booking FK, provider, provider_reference (unique where set),
  type (authorization|capture|refund), amount_minor, currency, status, idempotency_key (unique)
- payouts: profile FK, booking FK, amount_minor, currency, provider_reference, status
- conversations: booking FK. messages: conversation FK, sender FK, body, created_at, read_at
- reviews: booking FK, reviewer FK, profile FK, rating 1-5, comment, status;
  UNIQUE(booking, reviewer)
- safety_reports: reporter FK, reported FK, booking?, reason, description,
  status, assigned_admin?
- event_collections: title, slug, description, country_code?, city?,
  starts_at, ends_at, status. event_collection_experiences: collection FK,
  experience FK, sort_order
- audit_logs: actor FK, action, entity_type, entity_id, metadata, created_at
- plus: saved_companions, blocks, notification_records

## 6. Required DB constraints
```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;
ALTER TABLE bookings ADD CONSTRAINT no_overlapping_active_bookings
EXCLUDE USING gist (
  companion_profile_id WITH =,
  tstzrange(start_at, end_at, '[)') WITH &&
) WHERE (status IN ('awaiting_payment','confirmed','in_progress'));
```
`requested` does not block a slot. Back the constraint with transactions,
row locking, and hold expiry.
Also enforce: unique email, unique slugs, unique provider reference,
unique idempotency keys, unique review per booking+reviewer, end_at > start_at,
non-negative money, valid currency, PROTECT deletes on financial records.
Indexes: users.email; profiles slug/status; experiences status/profile/price;
bookings customer/profile/start_at/status; payments booking_id;
messages (conversation_id, created_at); reviews profile_id.
Validate with EXPLAIN ANALYZE before adding more.

## 7. API (base /api/v1/, JSON, versioned)
Conventions: cursor pagination, structured errors
`{"error":{"code":"BOOKING_SLOT_UNAVAILABLE","message":"..."}}`,
`Idempotency-Key` header on booking and payment creation, request
correlation IDs, rate limits, auth + object-level authorization on everything.
Auth: POST /auth/register, /auth/login, /auth/logout, /auth/password/reset,
/auth/password/confirm, /auth/email/verify; (P1) /auth/phone/verify.
Users: GET/PATCH /users/me.
Hosts: GET /companions, GET /companions/{slug}, POST /companions/applications,
GET/PATCH /companions/me.
Catalog: GET /categories; GET /experiences (filters above); GET
/experiences/{slug}; POST /experiences; PATCH /experiences/{id};
DELETE /experiences/{id} (deactivates); GET /collections, /collections/{slug}.
Availability: GET /companions/{id}/availability; GET /companions/me/availability;
POST /companions/me/availability/rules; PATCH/DELETE .../rules/{id};
POST .../availability/exceptions.
Bookings: POST /bookings; GET /bookings; GET /bookings/{id};
POST /bookings/{id}/{accept|decline|cancel|complete}; GET /bookings/{id}/events.
Booking request body: experience_id, start_at (UTC), duration_minutes,
booking_mode, timezone, customer_note.
Payments: POST /bookings/{id}/payment; GET /payments/{id};
POST /payments/refunds (authorized only); POST /webhooks/payments/{provider}.
Messaging: GET /conversations; GET/POST /conversations/{id}/messages;
POST /conversations/{id}/read; POST /users/{id}/block.
Reviews/safety: POST /bookings/{id}/review; GET /companions/{id}/reviews; POST /reports.
Admin: /admin/{companion-applications, verifications, experiences, bookings,
payments, payouts, refunds, reports, collections, audit-logs}, permission-gated.

## 8. Security and privacy
TLS, modern password hashing, secure cookies, CSRF, input validation,
ORM-parameterized queries, object-level access control, rate limiting,
validated uploads, admin MFA, secrets via env, dependency scanning, audit logs.
Privacy: minimal data, separate private identity data from public profile,
restrict verification records, encrypt sensitive fields where appropriate,
define retention/deletion schedule, record consent, no precise public location.

## 9. Test requirements
Unit: pricing, fees, transitions, cancellation rules, availability, permissions, refunds.
Integration: transactions, holds, payment adapter, webhooks, notifications, Celery tasks.
Concurrency: two overlapping requests for the same host, only one succeeds.
E2E: register -> apply -> verify -> approve -> publish -> search -> request
-> accept -> pay -> complete -> review. Also: cancellation, payment failure,
duplicate webhook, expired hold, blocked user, reported user.
Load (P1, k6 or Locust): search, profiles, auth, availability, booking creation.

## 10. Launch acceptance (all must pass)
Customer: register, verify eligibility, browse approved hosts, search,
see availability, submit both booking types, pay, get updates, cancel
per policy, report/block.
Host: apply, get approved, publish, manage availability, accept/decline,
manage bookings, see payout status.
Platform: no double booking, verified webhooks, safe duplicate events,
auditable refunds, reviews require completed bookings, admin actions logged,
reports investigable, backups restorable, booking and payment flows tested.

## 11. Open decisions (make configurable, document in docs/decisions.md)
Commission %, price min/max, payment provider and payout arrangement,
verification provider, launch cities, cancellation/refund windows,
booking acceptance deadline, support and emergency escalation, host
moderation standards, legal entity and marketplace obligations.
