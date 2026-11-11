import hashlib
import hmac
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    Booking,
    PaymentTransaction,
    PaymentWebhookEvent,
    Payout,
    Refund,
)
from .notifications import enqueue_email
from .services import transition_booking

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PaymentSession:
    provider_reference: str
    checkout_url: str


class PaymentAdapter(ABC):
    provider_name: str
    is_sandbox = False

    @abstractmethod
    def initiate(self, payment):
        raise NotImplementedError

    @abstractmethod
    def verify(self, raw_body, signature):
        raise NotImplementedError

    @abstractmethod
    def webhook(self, raw_body, signature):
        raise NotImplementedError

    @abstractmethod
    def refund(self, payment, refund):
        raise NotImplementedError


class SandboxPaymentAdapter(PaymentAdapter):
    provider_name = "sandbox"
    is_sandbox = True

    def __init__(self):
        if not settings.DEBUG or settings.APP_ENV == "production":
            raise ImproperlyConfigured("The sandbox payment adapter is disabled outside development.")

    def initiate(self, payment):
        return PaymentSession(
            provider_reference=f"sandbox-{payment.pk}",
            checkout_url=f"/payments/sandbox/{payment.pk}",
        )

    def verify(self, raw_body, signature):
        secret = settings.PAYMENT_WEBHOOK_SECRET
        if not secret:
            raise ImproperlyConfigured("PAYMENT_WEBHOOK_SECRET must be configured to verify payment webhooks.")
        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature or ""):
            raise ValidationError("Payment webhook signature is invalid.")
        try:
            event = json.loads(raw_body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("Payment webhook body must be valid JSON.") from exc
        if not isinstance(event, dict):
            raise ValidationError("Payment webhook body must be a JSON object.")
        return event

    def webhook(self, raw_body, signature):
        event = self.verify(raw_body, signature)
        required = {"event_id", "provider_reference", "status", "amount_minor", "currency"}
        if not required.issubset(event):
            raise ValidationError("Payment webhook is missing required fields.")
        if event["status"] not in {"authorized", "captured", "failed", "expired"}:
            raise ValidationError("Payment webhook contains an unsupported status.")
        if (
            not isinstance(event["event_id"], str)
            or not event["event_id"]
            or len(event["event_id"]) > 180
            or not isinstance(event["provider_reference"], str)
            or not event["provider_reference"]
            or not isinstance(event["amount_minor"], int)
            or isinstance(event["amount_minor"], bool)
            or event["amount_minor"] < 0
            or not isinstance(event["currency"], str)
            or len(event["currency"]) != 3
        ):
            raise ValidationError("Payment webhook fields are invalid.")
        return event

    def refund(self, payment, refund):
        return {"provider_reference": f"sandbox-refund-{refund.pk}"}

    def signed_event(self, event):
        raw_body = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(
            settings.PAYMENT_WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        return raw_body, signature


def get_payment_adapter(provider=None):
    provider = provider or settings.PAYMENTS_PROVIDER
    if provider == SandboxPaymentAdapter.provider_name:
        return SandboxPaymentAdapter()
    raise ImproperlyConfigured(
        f"Payment provider {provider!r} has no configured adapter. No live payment integration is installed."
    )


@transaction.atomic
def initiate_payment(*, booking_id, customer, idempotency_key):
    if not idempotency_key or len(idempotency_key) > 128:
        raise ValidationError("A valid idempotency key is required.")
    booking = Booking.objects.select_for_update().select_related("host__user", "experience").filter(
        pk=booking_id
    ).first()
    if booking is None:
        raise ValidationError("Booking not found.")
    if booking.customer_id != customer.pk:
        raise ValidationError("Only the customer can initiate this booking's payment.")
    if booking.status != Booking.Status.AWAITING_PAYMENT:
        raise ValidationError("Payment can only be initiated for a booking awaiting payment.")
    if booking.payment_deadline is None or booking.payment_deadline <= timezone.now():
        raise ValidationError("The payment hold has expired.")
    if booking.total_minor < 1:
        raise ValidationError("A payment cannot be initiated for a zero-value booking.")

    fingerprint = hashlib.sha256(
        f"{booking.pk}:{booking.total_minor}:{booking.currency}".encode("utf-8")
    ).hexdigest()
    existing = PaymentTransaction.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        if (
            existing.booking_id != booking.pk
            or existing.metadata.get("request_fingerprint") != fingerprint
        ):
            raise ValidationError("This idempotency key was already used for a different payment.")
        return existing
    active_payment = PaymentTransaction.objects.filter(
        booking=booking,
        transaction_type=PaymentTransaction.TransactionType.AUTHORIZATION,
        status__in=[PaymentTransaction.Status.PENDING, PaymentTransaction.Status.AUTHORIZED],
    ).first()
    if active_payment:
        return active_payment

    adapter = get_payment_adapter()
    payment = PaymentTransaction.objects.create(
        booking=booking,
        provider=adapter.provider_name,
        transaction_type=PaymentTransaction.TransactionType.AUTHORIZATION,
        amount_minor=booking.total_minor,
        currency=booking.currency,
        status=PaymentTransaction.Status.PENDING,
        idempotency_key=idempotency_key,
        metadata={"request_fingerprint": fingerprint, "sandbox": adapter.is_sandbox},
    )
    try:
        session = adapter.initiate(payment)
    except Exception:
        payment.delete()
        raise
    payment.provider_reference = session.provider_reference
    payment.metadata = {**payment.metadata, "checkout_url": session.checkout_url}
    payment.save(update_fields=["provider_reference", "metadata", "updated_at"])
    return payment


@transaction.atomic
def process_payment_webhook(provider, raw_body, signature):
    if len(raw_body) > 16384:
        raise ValidationError("Payment webhook body is too large.")
    adapter = get_payment_adapter(provider)
    event = adapter.webhook(raw_body, signature)
    previous_event = PaymentWebhookEvent.objects.filter(
        provider=provider, event_id=event["event_id"]
    ).first()
    if previous_event:
        if previous_event.payload != event:
            raise ValidationError("A payment webhook event ID was reused with different content.")
        return {"duplicate": True, "result": previous_event.result}

    payment = PaymentTransaction.objects.select_for_update().select_related(
        "booking__customer", "booking__host__user", "booking__experience"
    ).filter(
        provider=provider, provider_reference=event["provider_reference"]
    ).first()
    webhook_record = PaymentWebhookEvent.objects.create(
        provider=provider,
        event_id=event["event_id"],
        payment=payment,
        payload=event,
    )
    if payment is None:
        _finish_webhook(webhook_record, "unknown_reference")
        logger.warning("Verified payment webhook references an unknown transaction")
        return {"duplicate": False, "result": webhook_record.result}
    if event["amount_minor"] != payment.amount_minor or event["currency"] != payment.currency:
        _finish_webhook(webhook_record, "amount_mismatch")
        logger.error("Payment webhook amount or currency mismatch for transaction %s", payment.pk)
        return {"duplicate": False, "result": webhook_record.result}
    if event["status"] == "authorized" and payment.status == PaymentTransaction.Status.PENDING:
        payment.status = PaymentTransaction.Status.AUTHORIZED
        _save_payment_status(payment)
        _finish_webhook(webhook_record, "authorized")
        return {"duplicate": False, "result": webhook_record.result}
    if event["status"] == "captured":
        if payment.status == PaymentTransaction.Status.CAPTURED:
            _finish_webhook(webhook_record, "already_captured")
            return {"duplicate": False, "result": webhook_record.result}
        if payment.status != PaymentTransaction.Status.AUTHORIZED:
            _finish_webhook(webhook_record, "invalid_transition")
            logger.error("Captured payment %s has no matching authorization", payment.pk)
            return {"duplicate": False, "result": webhook_record.result}
        payment.status = PaymentTransaction.Status.CAPTURED
        _save_payment_status(payment)
        booking = payment.booking
        if (
            booking.status != Booking.Status.AWAITING_PAYMENT
            or booking.payment_deadline is None
            or booking.payment_deadline <= timezone.now()
        ):
            _finish_webhook(webhook_record, "late_capture")
            logger.error("Captured payment %s has no active booking hold", payment.pk)
            return {"duplicate": False, "result": webhook_record.result}
        transition_booking(booking.pk, Booking.Status.CONFIRMED)
        Payout.objects.get_or_create(
            booking=booking,
            defaults={
                "host": booking.host,
                "amount_minor": max(0, payment.amount_minor - booking.fee_minor),
                "currency": payment.currency,
                "status": Payout.Status.PENDING,
            },
        )
        _queue_payment_emails(payment, "payment_succeeded")
        from .tasks import send_upcoming_booking_reminder

        delay = max(0, int((booking.start_at - timezone.now()).total_seconds()) - 86400)
        transaction.on_commit(
            lambda booking_id=str(booking.pk), countdown=delay: send_upcoming_booking_reminder.apply_async(
                args=[booking_id], countdown=countdown
            ),
            robust=True,
        )
        _finish_webhook(webhook_record, "captured")
        return {"duplicate": False, "result": webhook_record.result}
    if event["status"] == "failed" and payment.status in {
        PaymentTransaction.Status.PENDING,
        PaymentTransaction.Status.AUTHORIZED,
    }:
        payment.status = PaymentTransaction.Status.FAILED
        payment.metadata = {**payment.metadata, "failure_reason": str(event.get("reason", "provider_failed"))[:180]}
        _save_payment_status(payment)
        _queue_payment_emails(payment, "payment_failed")
        _finish_webhook(webhook_record, "failed")
        return {"duplicate": False, "result": webhook_record.result}
    if event["status"] == "expired" and payment.status in {
        PaymentTransaction.Status.PENDING,
        PaymentTransaction.Status.AUTHORIZED,
    }:
        payment.status = PaymentTransaction.Status.EXPIRED
        _save_payment_status(payment)
        if payment.booking.status == Booking.Status.AWAITING_PAYMENT:
            transition_booking(payment.booking_id, Booking.Status.EXPIRED)
        _queue_payment_emails(payment, "payment_failed")
        _finish_webhook(webhook_record, "expired")
        return {"duplicate": False, "result": webhook_record.result}
    _finish_webhook(webhook_record, "invalid_transition")
    return {"duplicate": False, "result": webhook_record.result}


def _save_payment_status(payment):
    payment.save(update_fields=["status", "metadata", "updated_at"])


def _finish_webhook(event, result):
    event.result = result
    event.processed_at = timezone.now()
    event.save(update_fields=["result", "processed_at"])


def _queue_payment_emails(payment, event_type):
    booking = payment.booking
    payload = {"title": booking.snapshot.get("title", booking.experience.title)}
    for recipient in (booking.customer, booking.host.user):
        enqueue_email(recipient, event_type, "payment", payment.pk, payload)


@transaction.atomic
def complete_sandbox_payment(payment_id, customer, outcome):
    if outcome not in {"success", "failure", "expiry"}:
        raise ValidationError("Choose success, failure, or expiry.")
    payment = PaymentTransaction.objects.select_for_update().select_related("booking").filter(
        pk=payment_id
    ).first()
    if payment is None or payment.booking.customer_id != customer.pk:
        raise ValidationError("Payment not found.")
    adapter = get_payment_adapter(payment.provider)
    if not isinstance(adapter, SandboxPaymentAdapter):
        raise ValidationError("Sandbox completion is unavailable for this payment provider.")
    if outcome == "success":
        statuses = ("authorized", "captured")
    elif outcome == "failure":
        statuses = ("failed",)
    else:
        statuses = ("expired",)
    result = {}
    for status in statuses:
        event = {
            "event_id": f"sandbox-{payment.pk}-{status}",
            "provider_reference": payment.provider_reference,
            "status": status,
            "amount_minor": payment.amount_minor,
            "currency": payment.currency,
        }
        raw_body, signature = adapter.signed_event(event)
        result = process_payment_webhook(payment.provider, raw_body, signature)
    return result


@transaction.atomic
def create_refund(*, payment_id, actor, amount_minor, reason, idempotency_key):
    if not idempotency_key or len(idempotency_key) > 128:
        raise ValidationError("A valid idempotency key is required.")
    payment = PaymentTransaction.objects.select_for_update().select_related(
        "booking__experience", "booking__customer", "booking__host"
    ).filter(pk=payment_id).first()
    if payment is None:
        raise ValidationError("Payment not found.")
    existing = Refund.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        if (
            existing.payment_id != payment.pk
            or existing.amount_minor != amount_minor
            or existing.reason != reason
        ):
            raise ValidationError("This idempotency key was already used for a different refund.")
        return existing
    if payment.status not in {
        PaymentTransaction.Status.CAPTURED,
        PaymentTransaction.Status.PARTIALLY_REFUNDED,
    }:
        raise ValidationError("Only captured payments can be refunded.")
    refunded_amount = sum(
        payment.refunds.filter(status=Refund.Status.PROCESSED).values_list("amount_minor", flat=True)
    )
    remaining = payment.amount_minor - refunded_amount
    if amount_minor < 1 or amount_minor > remaining:
        raise ValidationError("Refund amount exceeds the remaining captured amount.")
    adapter = get_payment_adapter(payment.provider)
    refund = Refund.objects.create(
        payment=payment,
        amount_minor=amount_minor,
        currency=payment.currency,
        reason=reason,
        idempotency_key=idempotency_key,
        created_by=actor,
    )
    provider_result = adapter.refund(payment, refund)
    refund.provider_reference = provider_result["provider_reference"]
    refund.status = Refund.Status.PROCESSED
    refund.save(update_fields=["provider_reference", "status", "updated_at"])
    payment.status = (
        PaymentTransaction.Status.REFUNDED
        if amount_minor == remaining
        else PaymentTransaction.Status.PARTIALLY_REFUNDED
    )
    _save_payment_status(payment)
    Payout.objects.filter(booking=payment.booking).update(status=Payout.Status.REVERSED, updated_at=timezone.now())
    enqueue_email(
        payment.booking.customer,
        "payment_refunded",
        "refund",
        refund.pk,
        {"title": payment.booking.snapshot.get("title", payment.booking.experience.title)},
    )
    return refund
