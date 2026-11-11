from datetime import date, time, timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest import skipUnless
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import (
    AvailabilityRule,
    Category,
    Experience,
    HostProfile,
    ModerationQueueItem,
    User,
    VerificationCheck,
)
from .services import create_booking, transition_booking
from .permissions import IsBookingParty


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
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(
                executor.map(attempt, ["race-booking-a", "race-booking-b"])
            )

        self.assertCountEqual(outcomes, ["created", "conflict"])
