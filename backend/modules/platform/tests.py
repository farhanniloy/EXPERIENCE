from datetime import date, time, timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest import skipUnless
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import (
    AvailabilityException,
    AvailabilityRule,
    Booking,
    Category,
    Conversation,
    EventCollection,
    Experience,
    HostProfile,
    ModerationQueueItem,
    NotificationRecord,
    PaymentTransaction,
    PaymentWebhookEvent,
    Payout,
    Refund,
    Review,
    SafetyCheckIn,
    SafetyIncident,
    SafetyReport,
    AuditLog,
    TransactionalOutbox,
    User,
    VerificationCheck,
)
from .services import BookingSlotUnavailable, create_booking, transition_booking
from .permissions import IsBookingParty
from .notifications import enqueue_email
from .payments import SandboxPaymentAdapter, get_payment_adapter
from .tasks import deliver_outbox_event


class PlatformAPITests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            "customer@example.test", "Along-Customer-Password-391!", display_name="Casey"
        )
        self.host_user = User.objects.create_user(
            "host@example.test", "Along-Host-Password-391!", display_name="Host Sample"
        )
        self.host = HostProfile.objects.create(
            user=self.host_user.auth_user,
            slug="host-sample",
            city="Dhaka",
            status=HostProfile.Status.APPROVED,
            verified=True,
            languages=["English"],
        )
        AvailabilityRule.objects.bulk_create([
            AvailabilityRule(
                host=self.host,
                weekday=weekday,
                start_time=time(0, 0),
                end_time=time(23, 59),
                timezone="Asia/Dhaka",
            )
            for weekday in range(7)
        ])
        self.category = Category.objects.create(slug="movies", name="Movies", is_active=True)
        self.experience = Experience.objects.create(
            host=self.host,
            title="Cinema afternoon",
            slug="cinema-afternoon",
            summary="A public cinema outing.",
            description="Meet for a public screening.",
            duration_minutes=120,
            price_minor=1800,
            currency="BDT",
            status=Experience.Status.PUBLISHED,
            rating=4.8,
        )
        self.experience.categories.add(self.category)

    def test_registration_login_and_me(self):
        response = self.client.post(
            "/api/v1/auth/register",
            {
                "email": " New.User@example.test ",
                "display_name": "New User",
                "password": "Along-New-Password-123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["email"], "new.user@example.test")
        self.assertNotIn("password", response.data)

        self.client.logout()
        login_response = self.client.post(
            "/api/v1/auth/login",
            {"email": "customer@example.test", "password": "Along-Customer-Password-391!"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/users/me").status_code, 200)

        logout_response = self.client.post("/api/v1/auth/logout", {}, format="json")
        self.assertEqual(logout_response.status_code, 204)
        self.assertIn(self.client.get("/api/v1/users/me").status_code, {401, 403})

    def test_me_requires_authentication_and_only_updates_safe_fields(self):
        self.assertIn(self.client.get("/api/v1/users/me").status_code, {401, 403})
        self.client.force_authenticate(self.customer.auth_user)
        response = self.client.patch(
            "/api/v1/users/me",
            {"display_name": "Updated", "status": "suspended"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.display_name, "Updated")
        self.assertEqual(self.customer.status, User.Status.ACTIVE)

    def test_booking_party_permission_uses_authentication_user_ids(self):
        booking = self._create_booking()
        permission = IsBookingParty()

        self.assertTrue(
            permission.has_object_permission(
                SimpleNamespace(user=self.customer.auth_user), None, booking
            )
        )
        self.assertTrue(
            permission.has_object_permission(
                SimpleNamespace(user=self.host_user.auth_user), None, booking
            )
        )
        other_user = get_user_model().objects.create_user(
            username="unrelated", email="unrelated@example.test", password="Another-Password-391!"
        )
        self.assertFalse(
            permission.has_object_permission(SimpleNamespace(user=other_user), None, booking)
        )

    def test_password_reset_request_is_non_enumerating_and_sends_mail(self):
        response = self.client.post(
            "/api/v1/auth/password/reset",
            {"email": self.customer.email},
            format="json",
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(mail.outbox), 1)

        reset_url = mail.outbox[0].body.split("link to continue: ", 1)[1].strip()
        query = parse_qs(urlparse(reset_url).query)
        changed = self.client.post(
            "/api/v1/auth/password/confirm",
            {
                "email": self.customer.email,
                "token": query["token"][0],
                "new_password": "Along-Changed-Password-391!",
            },
            format="json",
        )
        self.assertEqual(changed.status_code, 200)
        self.assertTrue(
            self.client.post(
                "/api/v1/auth/login",
                {"email": self.customer.email, "password": "Along-Changed-Password-391!"},
                format="json",
            ).status_code
            == 200
        )
        self.assertIn("password reset link", mail.outbox[0].body)

        unknown = self.client.post(
            "/api/v1/auth/password/reset",
            {"email": "missing@example.test"},
            format="json",
        )
        self.assertEqual(unknown.status_code, 202)
        self.assertEqual(len(mail.outbox), 1)

    def test_catalog_filters_and_cursor_pagination(self):
        for index in range(21):
            experience = Experience.objects.create(
                host=self.host,
                title=f"Cinema afternoon {index}",
                slug=f"cinema-afternoon-{index}",
                summary="A public cinema outing.",
                description="Meet for a public screening.",
                duration_minutes=120,
                price_minor=1900,
                currency="BDT",
                status=Experience.Status.PUBLISHED,
                rating=4.5,
            )
            experience.categories.add(self.category)

        response = self.client.get(
            "/api/v1/experiences",
            {"category": "movies", "city": "dhaka", "budget": "2000", "sort": "price"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])

        invalid = self.client.get("/api/v1/experiences", {"budget": "-1"})
        self.assertEqual(invalid.status_code, 400)

    def test_category_and_host_reads_only_show_approved_public_data(self):
        response = self.client.get("/api/v1/categories")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["count"], 1)
        self.assertEqual(self.client.get("/api/v1/companions/host-sample").status_code, 200)
        self.host.status = HostProfile.Status.SUSPENDED
        self.host.save(update_fields=["status", "updated_at"])
        self.assertEqual(self.client.get("/api/v1/companions/host-sample").status_code, 404)

    def test_date_filter_uses_weekly_availability_and_validates_date(self):
        selected = date.today() + timedelta(days=1)
        AvailabilityRule.objects.create(
            host=self.host,
            weekday=selected.weekday(),
            start_time=time(10, 0),
            end_time=time(16, 0),
            timezone="Asia/Dhaka",
        )
        response = self.client.get("/api/v1/experiences", {"date": selected.isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        invalid = self.client.get("/api/v1/experiences", {"date": "tomorrow"})
        self.assertEqual(invalid.status_code, 400)

    def test_openapi_schema_is_available(self):
        response = self.client.get("/api/schema/")
        self.assertEqual(response.status_code, 200)

    def test_backend_root_redirects_to_api_docs(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/api/docs/", fetch_redirect_response=False)

    @override_settings(DEBUG=True)
    def test_host_application_requires_development_adult_confirmation(self):
        self.client.force_authenticate(self.customer.auth_user)
        profile = {
            "display_name": "Casey",
            "headline": "A thoughtful city explorer",
            "biography": "I enjoy public museums and cafés.",
            "city": "Dhaka",
            "languages": ["English"],
            "interests": ["Museums"],
            "photos": ["/placeholder-host.svg"],
        }
        saved = self.client.patch("/api/v1/companions/me", profile, format="json")
        self.assertEqual(saved.status_code, 200)
        denied = self.client.post(
            "/api/v1/companions/applications", profile, format="json"
        )
        self.assertEqual(denied.status_code, 400)
        verification = self.client.post(
            "/api/v1/companions/me/verification",
            {"confirmed_18": True},
            format="json",
        )
        self.assertEqual(verification.status_code, 201, verification.data)
        self.assertEqual(verification.data["provider"], "development_mock")
        submitted = self.client.post(
            "/api/v1/companions/applications", profile, format="json"
        )
        self.assertEqual(submitted.status_code, 202)
        self.assertEqual(submitted.data["status"], HostProfile.Status.SUBMITTED)
        self.assertTrue(
            ModerationQueueItem.objects.filter(
                host__user=self.customer.auth_user,
                queue_type=ModerationQueueItem.QueueType.HOST_APPLICATION,
                status=ModerationQueueItem.Status.PENDING,
            ).exists()
        )

    def test_host_profile_and_experience_reads_are_not_write_throttled(self):
        self.client.force_authenticate(self.host_user.auth_user)
        for endpoint, request_count in (
            ("/api/v1/companions/me", 11),
            ("/api/v1/experiences/manage", 31),
        ):
            for _ in range(request_count):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 200, response.data)

    @override_settings(DEBUG=True, APP_ENV="production")
    def test_development_verification_adapter_is_disabled_in_production(self):
        self.client.force_authenticate(self.customer.auth_user)
        response = self.client.post(
            "/api/v1/companions/me/verification",
            {"confirmed_18": True},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_host_cannot_publish_before_approval_and_owns_managed_experiences(self):
        self.client.force_authenticate(self.customer.auth_user)
        payload = {
            "title": "Public museum afternoon",
            "description": "Visit a public museum.",
            "duration_minutes": 120,
            "price_minor": 1800,
            "submit_for_review": True,
        }
        rejected = self.client.post("/api/v1/experiences/manage", payload, format="json")
        self.assertEqual(rejected.status_code, 403)
        payload["submit_for_review"] = False
        draft = self.client.post("/api/v1/experiences/manage", payload, format="json")
        self.assertEqual(draft.status_code, 201)
        self.assertEqual(draft.data["status"], Experience.Status.DRAFT)

        other = User.objects.create_user(
            "other-customer@example.test",
            "Along-Other-Password-391!",
            display_name="Other Customer",
        )
        self.client.force_authenticate(other.auth_user)
        forbidden = self.client.patch(
            f"/api/v1/experiences/manage/{draft.data['id']}",
            {"title": "Not owned"},
            format="json",
        )
        self.assertEqual(forbidden.status_code, 404)

    def test_first_listing_requires_moderation_and_admin_approval(self):
        host_account = User.objects.create_user(
            "new-host@example.test",
            "Along-New-Host-Password-391!",
            display_name="New Host",
        )
        host = HostProfile.objects.create(
            user=host_account.auth_user,
            slug="new-host",
            city="Dhaka",
            status=HostProfile.Status.APPROVED,
        )
        self.client.force_authenticate(host_account.auth_user)
        created = self.client.post(
            "/api/v1/experiences/manage",
            {
                "title": "Public art gallery visit",
                "description": "Explore a public gallery together.",
                "duration_minutes": 90,
                "price_minor": 1500,
                "submit_for_review": True,
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["status"], Experience.Status.PENDING_REVIEW)
        item = ModerationQueueItem.objects.get(experience_id=created.data["id"])
        self.assertEqual(item.queue_type, ModerationQueueItem.QueueType.FIRST_LISTING)
        self.client.force_authenticate(self.customer.auth_user)
        self.assertEqual(self.client.get("/api/v1/admin/moderation").status_code, 403)

        staff_user = get_user_model().objects.create_user(
            username="moderator",
            email="moderator@example.test",
            password="Along-Moderator-Password-391!",
            is_staff=True,
        )
        self.client.force_authenticate(staff_user)
        queue = self.client.get("/api/v1/admin/moderation")
        self.assertEqual(queue.status_code, 200)
        reviewed = self.client.post(
            f"/api/v1/admin/moderation/{item.pk}",
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(reviewed.status_code, 200)
        created_experience = Experience.objects.get(pk=created.data["id"])
        self.assertEqual(created_experience.status, Experience.Status.PUBLISHED)
        public_results = self.client.get(
            "/api/v1/experiences", {"q": "Public art gallery visit"}
        )
        self.assertIn(
            created_experience.slug,
            {item["slug"] for item in public_results.data["results"]},
        )
        host.refresh_from_db()
        self.assertEqual(host.status, HostProfile.Status.APPROVED)
        self.assertTrue(
            AuditLog.objects.filter(
                actor=staff_user,
                action="moderation_approve",
                entity_id=str(item.pk),
            ).exists()
        )

    def test_safety_checkin_creates_actionable_incident_and_reports_are_member_scoped(self):
        booking = self._create_booking()
        booking.status = Booking.Status.CONFIRMED
        booking.save(update_fields=["status"])
        self.client.force_authenticate(self.customer.auth_user)

        safe = self.client.post(
            f"/api/v1/bookings/{booking.pk}/check-in",
            {"status": SafetyCheckIn.Status.SAFE},
            format="json",
        )
        self.assertEqual(safe.status_code, 200, safe.data)
        self.assertFalse(safe.data["safety_team_notified"])

        needs_help = self.client.post(
            f"/api/v1/bookings/{booking.pk}/check-in",
            {"status": SafetyCheckIn.Status.NEEDS_HELP},
            format="json",
        )
        self.assertEqual(needs_help.status_code, 200, needs_help.data)
        self.assertTrue(needs_help.data["safety_team_notified"])
        self.assertEqual(SafetyCheckIn.objects.filter(booking=booking).count(), 1)
        self.assertEqual(SafetyReport.objects.filter(booking=booking).count(), 1)
        self.assertEqual(SafetyIncident.objects.filter(booking=booking).count(), 1)

        repeated = self.client.post(
            f"/api/v1/bookings/{booking.pk}/check-in",
            {"status": SafetyCheckIn.Status.NEEDS_HELP},
            format="json",
        )
        self.assertFalse(repeated.data["safety_team_notified"])
        self.assertEqual(SafetyReport.objects.filter(booking=booking).count(), 1)

        report = self.client.post(
            "/api/v1/reports",
            {
                "booking_id": str(booking.pk),
                "reason": "harassment",
                "description": "The other participant made me feel unsafe.",
            },
            format="json",
        )
        self.assertEqual(report.status_code, 201, report.data)
        outsider = User.objects.create_user(
            "outsider@example.test", "Along-Outsider-Password-391!"
        )
        self.client.force_authenticate(outsider.auth_user)
        forbidden = self.client.post(
            f"/api/v1/bookings/{booking.pk}/check-in",
            {"status": SafetyCheckIn.Status.SAFE},
            format="json",
        )
        self.assertEqual(forbidden.status_code, 403)
        staff_user = get_user_model().objects.create_user(
            username="safety-moderator",
            email="safety-moderator@example.test",
            password="Along-Safety-Moderator-391!",
            is_staff=True,
        )
        self.client.force_authenticate(staff_user)
        moderated = self.client.post(
            f"/api/v1/admin/reports/{report.data['id']}",
            {"action": "review", "resolution_notes": "Assigned for staff follow-up."},
            format="json",
        )
        self.assertEqual(moderated.status_code, 200, moderated.data)
        self.assertEqual(
            SafetyReport.objects.get(pk=report.data["id"]).status,
            SafetyReport.Status.REVIEWING,
        )
        self.assertTrue(
            AuditLog.objects.filter(
                actor=staff_user, action="safety_report_review", entity_id=report.data["id"]
            ).exists()
        )
        staff_suspend = self.client.post(
            f"/api/v1/admin/reports/{report.data['id']}",
            {"action": "suspend"},
            format="json",
        )
        self.assertEqual(staff_suspend.status_code, 403)
        superuser = get_user_model().objects.create_superuser(
            username="report-safety-superuser",
            email="report-safety-superuser@example.test",
            password="Along-Report-Superuser-391!",
        )
        self.client.force_authenticate(superuser)
        suspended_report = self.client.post(
            f"/api/v1/admin/reports/{report.data['id']}",
            {"action": "suspend", "resolution_notes": "Suspended pending investigation."},
            format="json",
        )
        self.assertEqual(suspended_report.status_code, 200, suspended_report.data)
        self.host_user.auth_user.refresh_from_db()
        self.assertFalse(self.host_user.auth_user.is_active)

    def test_reviews_require_completed_booking_and_are_verified_and_moderated(self):
        booking = self._create_booking()
        self.client.force_authenticate(self.customer.auth_user)
        payload = {
            "rating": 5,
            "comment": "A thoughtful public museum visit.",
            "private_safety_feedback": "Private detail for moderators only.",
        }
        premature = self.client.post(
            f"/api/v1/bookings/{booking.pk}/review", payload, format="json"
        )
        self.assertEqual(premature.status_code, 400)

        booking.status = Booking.Status.COMPLETED
        booking.save(update_fields=["status"])
        created = self.client.post(
            f"/api/v1/bookings/{booking.pk}/review", payload, format="json"
        )
        self.assertEqual(created.status_code, 201, created.data)
        self.assertTrue(created.data["verified_booking"])
        self.assertEqual(created.data["status"], Review.Status.PENDING)
        duplicate = self.client.post(
            f"/api/v1/bookings/{booking.pk}/review", payload, format="json"
        )
        self.assertEqual(duplicate.status_code, 400)

        public_path = f"/api/v1/companions/{self.host.slug}/reviews"
        self.assertEqual(self.client.get(public_path).data, [])
        staff_user = get_user_model().objects.create_user(
            username="review-moderator",
            email="review-moderator@example.test",
            password="Along-Review-Moderator-391!",
            is_staff=True,
        )
        self.client.force_authenticate(staff_user)
        moderated = self.client.post(
            f"/api/v1/admin/reviews/{created.data['id']}",
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(moderated.status_code, 200, moderated.data)
        public_reviews = self.client.get(public_path)
        self.assertEqual(public_reviews.status_code, 200)
        self.assertTrue(public_reviews.data[0]["verified_booking"])
        self.assertNotIn("private_safety_feedback", public_reviews.data[0])
        self.assertTrue(
            AuditLog.objects.filter(
                actor=staff_user, action="review_approved", entity_id=created.data["id"]
            ).exists()
        )
        self.client.force_authenticate(self.host_user.auth_user)
        review_report = self.client.post(
            "/api/v1/reports",
            {
                "review_id": created.data["id"],
                "reason": "review_content",
                "description": "Please review this feedback for a policy violation.",
            },
            format="json",
        )
        self.assertEqual(review_report.status_code, 201, review_report.data)
        self.assertEqual(
            str(SafetyReport.objects.get(pk=review_report.data["id"]).review_id),
            str(created.data["id"]),
        )

    def test_staff_console_permissions_suspension_and_verification_privacy(self):
        VerificationCheck.objects.create(
            user=self.customer.auth_user,
            provider="private-test-provider",
            provider_reference="private-reference-marker",
            check_type=VerificationCheck.CheckType.IDENTITY,
            status=VerificationCheck.Status.APPROVED,
            metadata={"private_document_marker": "must-not-be-returned"},
        )
        self.client.force_authenticate(self.customer.auth_user)
        self.assertEqual(self.client.get("/api/v1/admin/dashboard").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/users/me").status_code, 200)
        customer_json = str(self.client.get("/api/v1/users/me").data)
        self.assertNotIn("private-reference-marker", customer_json)
        self.assertNotIn("private_document_marker", customer_json)
        private_booking = self._create_booking()
        private_booking.meeting_location_private = "private-residential-address-marker"
        private_booking.save(update_fields=["meeting_location_private"])
        booking_response = self.client.get(f"/api/v1/bookings/{private_booking.pk}")
        self.assertEqual(booking_response.status_code, 200)
        self.assertNotIn("private-residential-address-marker", str(booking_response.data))
        public_profile = self.client.get(f"/api/v1/companions/{self.host.slug}")
        self.assertEqual(public_profile.status_code, 200)
        self.assertNotIn("private-reference-marker", str(public_profile.data))
        payment = PaymentTransaction.objects.create(
            booking=private_booking,
            provider="sandbox",
            transaction_type=PaymentTransaction.TransactionType.AUTHORIZATION,
            amount_minor=private_booking.total_minor,
            currency=private_booking.currency,
            idempotency_key="admin-dashboard-payment",
        )

        staff_user = get_user_model().objects.create_user(
            username="staff-safety",
            email="staff-safety@example.test",
            password="Along-Staff-Safety-391!",
            is_staff=True,
        )
        self.client.force_authenticate(staff_user)
        dashboard = self.client.get("/api/v1/admin/dashboard")
        self.assertEqual(dashboard.status_code, 200, dashboard.data)
        self.assertIn(str(private_booking.pk), {item["id"] for item in dashboard.data["bookings"]})
        self.assertIn(str(payment.pk), {item["id"] for item in dashboard.data["payments"]})
        self.assertNotIn("private-residential-address-marker", str(dashboard.data))
        denied = self.client.post(
            f"/api/v1/admin/accounts/{self.customer.pk}/suspension",
            {"status": User.Status.SUSPENDED},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)

        superuser = get_user_model().objects.create_superuser(
            username="safety-superuser",
            email="safety-superuser@example.test",
            password="Along-Safety-Superuser-391!",
        )
        self.client.force_authenticate(superuser)
        suspended = self.client.post(
            f"/api/v1/admin/accounts/{self.customer.pk}/suspension",
            {"status": User.Status.SUSPENDED},
            format="json",
        )
        self.assertEqual(suspended.status_code, 200, suspended.data)
        self.customer.refresh_from_db()
        self.customer.auth_user.refresh_from_db()
        self.assertEqual(self.customer.status, User.Status.SUSPENDED)
        self.assertFalse(self.customer.auth_user.is_active)
        self.assertTrue(
            AuditLog.objects.filter(
                actor=superuser, action="account_suspended", entity_id=str(self.customer.pk)
            ).exists()
        )

    def test_expired_event_collections_are_deactivated_on_public_access(self):
        expired = EventCollection.objects.create(
            title="Expired collection",
            slug="expired-stage-seven",
            status=EventCollection.Status.ACTIVE,
            starts_at=timezone.now() - timedelta(days=2),
            ends_at=timezone.now() - timedelta(days=1),
        )
        response = self.client.get("/api/v1/collections")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(expired.slug, {item["slug"] for item in response.data["results"]})
        expired.refresh_from_db()
        self.assertEqual(expired.status, EventCollection.Status.INACTIVE)

    def test_flagged_listing_is_held_in_moderation_queue(self):
        self.client.force_authenticate(self.host_user.auth_user)
        response = self.client.post(
            "/api/v1/experiences/manage",
            {
                "title": "Museum visit",
                "description": "Message me on WhatsApp at 01712345678.",
                "duration_minutes": 90,
                "price_minor": 1500,
                "submit_for_review": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Experience.Status.PENDING_REVIEW)
        item = ModerationQueueItem.objects.get(experience_id=response.data["id"])
        self.assertIn("description", item.flagged_fields)
        self.assertIn("WhatsApp", item.experience.description)
        staff_user = get_user_model().objects.create_user(
            username="content-moderator",
            email="content-moderator@example.test",
            password="Along-Content-Moderator-391!",
            is_staff=True,
        )
        self.client.force_authenticate(staff_user)
        queue = self.client.get("/api/v1/admin/moderation")
        queued_item = next(entry for entry in queue.data if entry["id"] == str(item.pk))
        self.assertIn("WhatsApp", queued_item["content"]["description"])

    def test_flagged_profile_content_is_hidden_and_review_queued(self):
        self.client.force_authenticate(self.host_user.auth_user)
        response = self.client.patch(
            "/api/v1/companions/me",
            {"biography": "Contact me on WhatsApp at 01712345678."},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], HostProfile.Status.UNDER_REVIEW)
        item = ModerationQueueItem.objects.get(
            host=self.host,
            queue_type=ModerationQueueItem.QueueType.PROFILE_CONTENT,
            status=ModerationQueueItem.Status.PENDING,
        )
        self.assertIn("biography", item.flagged_fields)
        self.assertEqual(
            self.client.get("/api/v1/companions/host-sample").status_code, 404
        )

    def test_customer_and_host_dashboards_return_real_account_data(self):
        self.client.force_authenticate(self.customer.auth_user)
        customer_dashboard = self.client.get("/api/v1/dashboard")
        self.assertEqual(customer_dashboard.status_code, 200)
        self.assertEqual(customer_dashboard.data["display_name"], "Casey")
        host_dashboard = self.client.get("/api/v1/dashboard/companion")
        self.assertEqual(host_dashboard.status_code, 200)
        self.assertEqual(host_dashboard.data["host"]["status"], HostProfile.Status.DRAFT)

    def test_booking_state_machine_records_transition_events(self):
        booking = self._create_booking()
        transition_booking(booking.id, "awaiting_payment", actor=self.customer.auth_user)
        booking.refresh_from_db()
        self.assertEqual(booking.status, "awaiting_payment")
        self.assertEqual(booking.events.count(), 1)
        with self.assertRaises(ValidationError):
            transition_booking(booking.id, "completed", actor=self.customer.auth_user)

    def test_booking_api_is_idempotent_and_requires_matching_key_payload(self):
        self.client.force_authenticate(self.customer.auth_user)
        VerificationCheck.objects.create(
            user=self.customer.auth_user,
            provider="sample",
            check_type=VerificationCheck.CheckType.AGE,
            status=VerificationCheck.Status.APPROVED,
        )
        start = timezone.now() + timedelta(days=5)
        payload = {
            "experience_id": str(self.experience.id),
            "start_at": start.isoformat(),
            "duration_minutes": 120,
            "booking_mode": "request",
            "timezone": "Asia/Dhaka",
            "public_venue_name": "Dhaka public cinema",
            "customer_note": "Meet by the public entrance.",
        }
        headers = {"HTTP_IDEMPOTENCY_KEY": "booking-api-idempotency-1"}
        first = self.client.post("/api/v1/bookings", payload, format="json", **headers)
        self.assertEqual(first.status_code, 201, first.data)
        duplicate = self.client.post("/api/v1/bookings", payload, format="json", **headers)
        self.assertEqual(duplicate.status_code, 201, duplicate.data)
        self.assertEqual(first.data["id"], duplicate.data["id"])
        self.assertEqual(Booking.objects.filter(customer=self.customer.auth_user).count(), 1)

        payload["public_venue_name"] = "Different public venue"
        mismatch = self.client.post("/api/v1/bookings", payload, format="json", **headers)
        self.assertEqual(mismatch.status_code, 400)
        self.assertEqual(Booking.objects.filter(customer=self.customer.auth_user).count(), 1)

    @override_settings(BOOKING_HOLD_MINUTES=15)
    def test_expired_payment_hold_releases_slot(self):
        from .tasks import expire_booking_hold

        self.client.force_authenticate(self.customer.auth_user)
        VerificationCheck.objects.create(
            user=self.customer.auth_user,
            provider="sample",
            check_type=VerificationCheck.CheckType.AGE,
            status=VerificationCheck.Status.APPROVED,
        )
        self.experience.instant_booking_enabled = True
        self.experience.save(update_fields=["instant_booking_enabled", "updated_at"])
        start = timezone.now() + timedelta(days=6)
        payload = {
            "experience_id": str(self.experience.id),
            "start_at": start.isoformat(),
            "duration_minutes": 120,
            "booking_mode": "instant",
            "timezone": "Asia/Dhaka",
            "public_venue_name": "Dhaka public cinema",
        }
        first = self.client.post(
            "/api/v1/bookings",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="booking-expiry-first",
        )
        self.assertEqual(first.status_code, 201, first.data)
        booking = Booking.objects.get(pk=first.data["id"])
        self.assertEqual(booking.status, Booking.Status.AWAITING_PAYMENT)
        booking.payment_deadline = timezone.now() - timedelta(seconds=1)
        booking.save(update_fields=["payment_deadline", "updated_at"])
        self.assertTrue(expire_booking_hold.run(str(booking.pk)))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.EXPIRED)
        self.assertEqual(booking.events.count(), 2)

        second = self.client.post(
            "/api/v1/bookings",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="booking-expiry-second",
        )
        self.assertEqual(second.status_code, 201, second.data)

    def test_booking_action_permissions_and_invalid_transitions(self):
        booking = self._create_booking()
        self.client.force_authenticate(self.customer.auth_user)
        forbidden = self.client.post(f"/api/v1/bookings/{booking.id}/accept", {}, format="json")
        self.assertEqual(forbidden.status_code, 403)
        self.client.force_authenticate(self.host_user.auth_user)
        invalid = self.client.post(f"/api/v1/bookings/{booking.id}/complete", {}, format="json")
        self.assertEqual(invalid.status_code, 400)
        accepted = self.client.post(f"/api/v1/bookings/{booking.id}/accept", {}, format="json")
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertEqual(accepted.data["status"], Booking.Status.AWAITING_PAYMENT)

    def test_availability_rules_preferences_and_exceptions_are_owner_scoped(self):
        self.client.force_authenticate(self.host_user.auth_user)
        preferences = self.client.patch(
            "/api/v1/companions/me/availability/preferences",
            {"minimum_notice_hours": 4, "max_advance_days": 45, "buffer_minutes": 30},
            format="json",
        )
        self.assertEqual(preferences.status_code, 200)
        self.host.refresh_from_db()
        self.assertEqual(self.host.minimum_notice_hours, 4)
        self.assertEqual(self.host.buffer_minutes, 30)

        created = self.client.post(
            "/api/v1/companions/me/availability/rules",
            {
                "weekday": 0,
                "start_time": "09:00",
                "end_time": "17:00",
                "timezone": "Asia/Dhaka",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        other = User.objects.create_user(
            "availability-other@example.test",
            "Along-Availability-Password-391!",
            display_name="Other",
        )
        self.client.force_authenticate(other.auth_user)
        forbidden = self.client.delete(
            f"/api/v1/companions/me/availability/rules/{created.data['id']}"
        )
        self.assertEqual(forbidden.status_code, 404)

        self.client.force_authenticate(self.host_user.auth_user)
        exception_start = timezone.now() + timedelta(days=2)
        exception = self.client.post(
            "/api/v1/companions/me/availability/exceptions",
            {
                "start_at": exception_start.isoformat(),
                "end_at": (exception_start + timedelta(hours=2)).isoformat(),
                "exception_type": AvailabilityException.ExceptionType.UNAVAILABLE,
                "notes": "Personal time",
            },
            format="json",
        )
        self.assertEqual(exception.status_code, 201, exception.data)
        self.assertEqual(self.client.get("/api/v1/companions/me/availability").status_code, 200)

    def test_public_availability_applies_notice_and_never_exposes_booking_details(self):
        start_day = (timezone.now() + timedelta(days=3)).date()
        response = self.client.get(
            f"/api/v1/experiences/{self.experience.slug}/availability",
            {
                "from": start_day.isoformat(),
                "to": start_day.isoformat(),
                "timezone": "Asia/Dhaka",
                "duration_minutes": 120,
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data)
        self.assertEqual(set(response.data[0]), {"start_at", "end_at", "timezone"})
        self.assertNotIn("customer", response.data[0])

    def test_booking_service_uses_server_price_and_requires_age_and_public_venue(self):
        VerificationCheck.objects.create(
            user=self.customer.auth_user,
            provider="sample",
            check_type=VerificationCheck.CheckType.AGE,
            status=VerificationCheck.Status.APPROVED,
        )
        self.experience.instant_booking_enabled = True
        self.experience.save(update_fields=["instant_booking_enabled", "updated_at"])
        start = timezone.now() + timedelta(days=5)
        booking = create_booking(
            customer=self.customer.auth_user,
            host=self.host,
            experience=self.experience,
            start_at=start,
            end_at=start + timedelta(hours=2),
            idempotency_key="service-booking-1",
            timezone_name="Asia/Dhaka",
            booking_mode="instant",
            public_venue_name="Dhaka public cinema",
        )
        self.assertEqual(booking.status, "awaiting_payment")
        self.assertEqual(booking.total_minor, self.experience.price_minor)
        self.assertIsNotNone(booking.payment_deadline)
        repeated = create_booking(
            customer=self.customer.auth_user,
            host=self.host,
            experience=self.experience,
            start_at=start,
            end_at=start + timedelta(hours=2),
            idempotency_key="service-booking-1",
            timezone_name="Asia/Dhaka",
            booking_mode="instant",
            public_venue_name="Dhaka public cinema",
        )
        self.assertEqual(repeated.pk, booking.pk)

    @override_settings(
        DEBUG=True,
        APP_ENV="development",
        PAYMENTS_PROVIDER="sandbox",
        PAYMENT_WEBHOOK_SECRET="test-payment-signing-key",
    )
    def test_payment_creation_is_idempotent_and_browser_get_cannot_confirm_booking(self):
        booking = self._make_payable_booking()
        self.client.force_authenticate(self.customer.auth_user)
        path = f"/api/v1/bookings/{booking.pk}/payment"
        first = self.client.post(
            path, {}, format="json", HTTP_IDEMPOTENCY_KEY="payment-idempotency-1"
        )
        self.assertEqual(first.status_code, 201, first.data)
        duplicate = self.client.post(
            path, {}, format="json", HTTP_IDEMPOTENCY_KEY="payment-idempotency-1"
        )
        self.assertEqual(duplicate.status_code, 201, duplicate.data)
        self.assertEqual(first.data["id"], duplicate.data["id"])
        self.assertEqual(PaymentTransaction.objects.filter(booking=booking).count(), 1)
        self.assertIn("development only", first.data["provider_label"])

        redirect_result = self.client.get(
            f"/api/v1/payments/{first.data['id']}/sandbox-complete?outcome=success"
        )
        payment_status = self.client.get(f"/api/v1/payments/{first.data['id']}")
        booking.refresh_from_db()
        self.assertEqual(redirect_result.status_code, 405)
        self.assertEqual(payment_status.data["status"], PaymentTransaction.Status.PENDING)
        self.assertEqual(booking.status, Booking.Status.AWAITING_PAYMENT)

    @override_settings(
        DEBUG=True,
        APP_ENV="development",
        PAYMENTS_PROVIDER="sandbox",
        PAYMENT_WEBHOOK_SECRET="test-payment-signing-key",
    )
    def test_signed_webhook_confirms_only_after_authorization_and_is_replay_safe(self):
        booking = self._make_payable_booking()
        self.client.force_authenticate(self.customer.auth_user)
        initiated = self.client.post(
            f"/api/v1/bookings/{booking.pk}/payment",
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY="payment-webhook-initiate",
        )
        self.assertEqual(initiated.status_code, 201, initiated.data)
        payment = PaymentTransaction.objects.get(pk=initiated.data["id"])

        invalid_capture = self._post_payment_webhook(payment, "capture-before-auth", "captured")
        self.assertEqual(invalid_capture.data["result"], "invalid_transition")
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.AWAITING_PAYMENT)

        authorized = self._post_payment_webhook(payment, "payment-authorized", "authorized")
        self.assertEqual(authorized.status_code, 200)
        captured = self._post_payment_webhook(payment, "payment-captured", "captured")
        self.assertEqual(captured.data["result"], "captured")
        replay = self._post_payment_webhook(payment, "payment-captured", "captured")
        self.assertTrue(replay.data["duplicate"])

        booking.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        self.assertEqual(payment.status, PaymentTransaction.Status.CAPTURED)
        self.assertEqual(Payout.objects.filter(booking=booking).count(), 1)
        self.assertEqual(PaymentWebhookEvent.objects.filter(payment=payment).count(), 3)

        payload = {
            "event_id": "invalid-signature",
            "provider_reference": payment.provider_reference,
            "status": "captured",
            "amount_minor": payment.amount_minor,
            "currency": payment.currency,
        }
        raw_body, _ = SandboxPaymentAdapter().signed_event(payload)
        rejected = self.client.generic(
            "POST",
            "/api/v1/webhooks/payments/sandbox",
            data=raw_body,
            content_type="application/json",
            HTTP_X_PAYMENT_SIGNATURE="not-a-valid-signature",
        )
        self.assertEqual(rejected.status_code, 400)

    @override_settings(
        DEBUG=True,
        APP_ENV="development",
        PAYMENTS_PROVIDER="sandbox",
        PAYMENT_WEBHOOK_SECRET="test-payment-signing-key",
    )
    def test_sandbox_failure_and_expiry_release_only_the_expired_booking(self):
        booking = self._make_payable_booking()
        self.client.force_authenticate(self.customer.auth_user)
        started = self.client.post(
            f"/api/v1/bookings/{booking.pk}/payment",
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY="payment-expiry-initiate",
        )
        self.assertEqual(started.status_code, 201)
        failed = self.client.post(
            f"/api/v1/payments/{started.data['id']}/sandbox-complete",
            {"outcome": "failure"},
            format="json",
        )
        self.assertEqual(failed.status_code, 200)
        self.assertEqual(failed.data["status"], PaymentTransaction.Status.FAILED)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.AWAITING_PAYMENT)

        retry = self.client.post(
            f"/api/v1/bookings/{booking.pk}/payment",
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY="payment-expiry-retry",
        )
        self.assertEqual(retry.status_code, 201)
        expired = self.client.post(
            f"/api/v1/payments/{retry.data['id']}/sandbox-complete",
            {"outcome": "expiry"},
            format="json",
        )
        self.assertEqual(expired.data["status"], PaymentTransaction.Status.EXPIRED)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.EXPIRED)

    @override_settings(
        DEBUG=True,
        APP_ENV="development",
        PAYMENTS_PROVIDER="sandbox",
        PAYMENT_WEBHOOK_SECRET="test-payment-signing-key",
    )
    def test_refunds_are_staff_only_idempotent_and_reverse_payout_records(self):
        booking, payment = self._capture_booking_payment("refund-payment")
        self.client.force_authenticate(self.customer.auth_user)
        payload = {
            "payment_id": str(payment.pk),
            "amount_minor": 500,
            "reason": "Approved customer refund",
        }
        denied = self.client.post(
            "/api/v1/payments/refunds",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="refund-key-1",
        )
        self.assertEqual(denied.status_code, 403)

        staff_user = get_user_model().objects.create_user(
            username="finance-staff", email="finance-staff@example.test", password="Along-Staff-Password-391!", is_staff=True
        )
        self.client.force_authenticate(staff_user)
        first = self.client.post(
            "/api/v1/payments/refunds",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="refund-key-1",
        )
        second = self.client.post(
            "/api/v1/payments/refunds",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="refund-key-1",
        )
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(Refund.objects.filter(payment=payment).count(), 1)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.Status.PARTIALLY_REFUNDED)
        self.assertEqual(Payout.objects.get(booking=booking).status, Payout.Status.REVERSED)

    @override_settings(DEBUG=False, APP_ENV="production", PAYMENTS_PROVIDER="sandbox")
    def test_sandbox_adapter_refuses_production_settings(self):
        with self.assertRaises(ImproperlyConfigured):
            get_payment_adapter("sandbox")

    def test_conversations_enforce_membership_read_state_and_blocking(self):
        booking = self._create_booking()
        conversation = Conversation.objects.create(booking=booking)
        other = User.objects.create_user(
            "conversation-outsider@example.test",
            "Along-Conversation-Password-391!",
            display_name="Conversation Outsider",
        )

        self.client.force_authenticate(other.auth_user)
        self.assertEqual(
            self.client.get(f"/api/v1/conversations/{conversation.pk}/messages").status_code,
            404,
        )
        self.assertEqual(self.client.get("/api/v1/conversations").data, [])

        self.client.force_authenticate(self.customer.auth_user)
        created = self.client.post(
            f"/api/v1/conversations/{conversation.pk}/messages",
            {"body": "I will meet you by the museum entrance."},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["moderation_status"], "visible")
        self.client.force_authenticate(self.host_user.auth_user)
        inbox = self.client.get("/api/v1/conversations")
        self.assertEqual(inbox.data[0]["unread_count"], 1)
        messages = self.client.get(f"/api/v1/conversations/{conversation.pk}/messages")
        self.assertEqual(messages.data[0]["body"], "I will meet you by the museum entrance.")
        marked = self.client.post(f"/api/v1/conversations/{conversation.pk}/read", {}, format="json")
        self.assertEqual(marked.data["marked_read"], 1)
        self.assertEqual(self.client.get("/api/v1/conversations").data[0]["unread_count"], 0)

        self.client.force_authenticate(self.customer.auth_user)
        blocked = self.client.post(
            f"/api/v1/users/{self.host_user.id}/block", {}, format="json"
        )
        self.assertEqual(blocked.status_code, 201)
        prevented = self.client.post(
            f"/api/v1/conversations/{conversation.pk}/messages",
            {"body": "This message should not be sent."},
            format="json",
        )
        self.assertEqual(prevented.status_code, 400)
        start = timezone.now() + timedelta(days=4)
        with self.assertRaisesMessage(ValidationError, "This host is unavailable for booking."):
            create_booking(
                customer=self.customer.auth_user,
                host=self.host,
                experience=self.experience,
                start_at=start,
                end_at=start + timedelta(hours=2),
                idempotency_key="blocked-user-booking",
                timezone_name="Asia/Dhaka",
                booking_mode="request",
                public_venue_name="Dhaka public cinema",
            )

    def test_flagged_messages_are_hidden_and_sent_to_moderation(self):
        booking = self._create_booking()
        conversation = Conversation.objects.create(booking=booking)
        self.client.force_authenticate(self.customer.auth_user)
        flagged = self.client.post(
            f"/api/v1/conversations/{conversation.pk}/messages",
            {"body": "Contact me on WhatsApp at 01712345678"},
            format="json",
        )
        self.assertEqual(flagged.status_code, 201, flagged.data)
        self.assertEqual(flagged.data["moderation_status"], "pending")
        self.client.force_authenticate(self.host_user.auth_user)
        hidden = self.client.get(f"/api/v1/conversations/{conversation.pk}/messages")
        self.assertEqual(hidden.data[0]["body"], "")

        moderator = get_user_model().objects.create_user(
            username="message-moderator",
            email="message-moderator@example.test",
            password="Along-Moderator-Password-391!",
            is_staff=True,
        )
        self.client.force_authenticate(moderator)
        queue = self.client.get("/api/v1/admin/moderation")
        item = next(entry for entry in queue.data if entry["queue_type"] == "message_content")
        self.assertEqual(item["content"]["body"], "Contact me on WhatsApp at 01712345678")
        review = self.client.post(
            f"/api/v1/admin/moderation/{item['id']}",
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(review.status_code, 200)
        self.client.force_authenticate(self.host_user.auth_user)
        visible = self.client.get(f"/api/v1/conversations/{conversation.pk}/messages")
        self.assertEqual(visible.data[0]["body"], "Contact me on WhatsApp at 01712345678")

    def test_transactional_outbox_delivers_email_once(self):
        event = enqueue_email(
            self.customer.auth_user,
            "booking_confirmed",
            "booking",
            "outbox-test-booking",
            {"title": "Museum visit"},
            key="outbox-test-booking-confirmed",
        )
        self.assertEqual(TransactionalOutbox.objects.filter(pk=event.pk).count(), 1)
        self.assertTrue(deliver_outbox_event.run(str(event.pk)))
        self.assertFalse(deliver_outbox_event.run(str(event.pk)))
        event.refresh_from_db()
        self.assertIsNotNone(event.processed_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(NotificationRecord.objects.filter(user=self.customer.auth_user).count(), 1)

    def _make_payable_booking(self):
        booking = self._create_booking()
        booking.status = Booking.Status.AWAITING_PAYMENT
        booking.payment_deadline = timezone.now() + timedelta(minutes=15)
        booking.save(update_fields=["status", "payment_deadline", "updated_at"])
        return booking

    def _signed_event_post(self, payload, signature=None):
        adapter = SandboxPaymentAdapter()
        raw_body, signed = adapter.signed_event(payload)
        return self.client.generic(
            "POST",
            "/api/v1/webhooks/payments/sandbox",
            data=raw_body,
            content_type="application/json",
            HTTP_X_PAYMENT_SIGNATURE=signature or signed,
        )

    def _post_payment_webhook(self, payment, event_id, provider_status):
        return self._signed_event_post({
            "event_id": event_id,
            "provider_reference": payment.provider_reference,
            "status": provider_status,
            "amount_minor": payment.amount_minor,
            "currency": payment.currency,
        })

    def _capture_booking_payment(self, key_prefix):
        booking = self._make_payable_booking()
        self.client.force_authenticate(self.customer.auth_user)
        response = self.client.post(
            f"/api/v1/bookings/{booking.pk}/payment",
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY=f"{key_prefix}-init",
        )
        self.assertEqual(response.status_code, 201, response.data)
        payment = PaymentTransaction.objects.get(pk=response.data["id"])
        self._post_payment_webhook(payment, f"{key_prefix}-auth", "authorized")
        self._post_payment_webhook(payment, f"{key_prefix}-capture", "captured")
        payment.refresh_from_db()
        return booking, payment

    def _create_booking(self):
        from .models import Booking

        start = timezone.now() + timedelta(days=4)
        return Booking.objects.create(
            customer=self.customer.auth_user,
            host=self.host,
            experience=self.experience,
            start_at=start,
            end_at=start + timedelta(hours=2),
            status=Booking.Status.REQUESTED,
            currency="BDT",
            base_price_minor=1800,
            total_minor=1800,
            public_venue_name="Dhaka public cinema",
            idempotency_key="test-booking-1",
        )


@skipUnless(connection.vendor == "postgresql", "booking overlap relies on PostgreSQL exclusion constraints")
class BookingOverlapRaceTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.account = User.objects.create_user(
            "race-customer@example.test",
            "Along-Race-Password-391!",
            display_name="Race Customer",
        )
        host_account = User.objects.create_user(
            "race-host@example.test",
            "Along-Race-Password-391!",
            display_name="Race Host",
        )
        host = HostProfile.objects.create(
            user=host_account.auth_user,
            slug="race-host",
            city="Dhaka",
            status=HostProfile.Status.APPROVED,
        )
        AvailabilityRule.objects.bulk_create([
            AvailabilityRule(
                host=host,
                weekday=weekday,
                start_time=time(0, 0),
                end_time=time(23, 59),
                timezone="Asia/Dhaka",
            )
            for weekday in range(7)
        ])
        self.experience = Experience.objects.create(
            host=host,
            title="Race test experience",
            slug="race-test-experience",
            description="A public meetup.",
            duration_minutes=60,
            price_minor=1000,
            instant_booking_enabled=True,
            status=Experience.Status.PUBLISHED,
        )
        VerificationCheck.objects.create(
            user=self.account.auth_user,
            provider="sample",
            check_type=VerificationCheck.CheckType.AGE,
            status=VerificationCheck.Status.APPROVED,
        )
        self.host = host
        self.start_at = timezone.now() + timedelta(days=3)

    def test_concurrent_bookings_cannot_hold_the_same_host_slot(self):
        barrier = Barrier(2)

        def attempt(idempotency_key):
            try:
                barrier.wait(timeout=10)
                create_booking(
                    customer=self.account.auth_user,
                    host=self.host,
                    experience=self.experience,
                    start_at=self.start_at,
                    end_at=self.start_at + timedelta(hours=1),
                    idempotency_key=idempotency_key,
                    timezone_name="Asia/Dhaka",
                    booking_mode="instant",
                    public_venue_name="Dhaka public cinema",
                )
                return "created"
            except IntegrityError:
                return "conflict"
            except BookingSlotUnavailable:
                return "conflict"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(
                executor.map(attempt, ["race-booking-a", "race-booking-b"])
            )

        self.assertCountEqual(outcomes, ["created", "conflict"])
