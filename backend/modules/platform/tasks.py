import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import Booking, BookingEvent, NotificationRecord, TransactionalOutbox

logger = logging.getLogger(__name__)


@shared_task
def expire_booking_hold(booking_id):
    with transaction.atomic():
        booking = Booking.objects.select_for_update().select_related(
            "customer", "host__user", "experience"
        ).filter(pk=booking_id).first()
        if (
            booking is None
            or booking.status != Booking.Status.AWAITING_PAYMENT
            or booking.payment_deadline is None
            or booking.payment_deadline > timezone.now()
        ):
            return False
        previous_status = booking.status
        booking.status = Booking.Status.EXPIRED
        booking.payment_deadline = None
        booking.save(update_fields=["status", "payment_deadline", "updated_at"])
        BookingEvent.objects.create(
            booking=booking,
            event_type="status_changed",
            previous_state=previous_status,
            new_state=booking.status,
            metadata={"reason": "payment_hold_expired"},
        )
        from .notifications import enqueue_email

        for recipient in (booking.customer, booking.host.user):
            enqueue_email(
                recipient,
                "payment_failed",
                "booking",
                booking.pk,
                {"title": booking.snapshot.get("title", booking.experience.title)},
            )
        return True


@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def deliver_outbox_event(self, event_id):
    retry_error = None
    with transaction.atomic():
        event = TransactionalOutbox.objects.select_for_update().select_related("recipient").filter(
            pk=event_id
        ).first()
        if event is None or event.processed_at is not None:
            return False
        event.attempts += 1
        event.save(update_fields=["attempts"])
        subject, body = _email_content(event.event_type, event.payload)
        recipient = event.recipient.email
        try:
            sent = send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [recipient],
                fail_silently=False,
            )
            if sent != 1:
                raise RuntimeError(f"Email backend reported {sent} delivered messages.")
        except Exception as exc:
            event.last_error = str(exc)[:500]
            event.save(update_fields=["last_error"])
            logger.exception("Email delivery failed for outbox event %s", event.pk)
            retry_error = exc
        else:
            NotificationRecord.objects.create(
                user=event.recipient,
                notification_type=event.event_type,
                payload=event.payload,
                sent_at=timezone.now(),
            )
            event.processed_at = timezone.now()
            event.last_error = ""
            event.save(update_fields=["processed_at", "last_error"])
    if retry_error:
        raise self.retry(exc=retry_error) from retry_error
    return True


def _email_content(event_type, payload):
    from .notifications import EMAIL_CONTENT

    subject, body = EMAIL_CONTENT[event_type]
    title = payload.get("title")
    state = payload.get("status")
    if title:
        body = f"{body}\n\nExperience: {title}"
    if state:
        body = f"{body}\n\nStatus: {state.replace('_', ' ').capitalize()}"
    return subject, body


@shared_task
def send_upcoming_booking_reminder(booking_id):
    booking = Booking.objects.select_related("customer", "host__user").filter(
        pk=booking_id,
        status=Booking.Status.CONFIRMED,
        start_at__gt=timezone.now(),
    ).first()
    if booking is None:
        return False
    from .notifications import enqueue_email

    for recipient in (booking.customer, booking.host.user):
        enqueue_email(
            recipient,
            "upcoming_booking",
            "booking",
            booking.pk,
            {"title": booking.snapshot.get("title", booking.experience.title)},
        )
    return True
