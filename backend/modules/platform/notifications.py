import logging

from django.db import transaction

from .models import TransactionalOutbox

logger = logging.getLogger(__name__)

EMAIL_CONTENT = {
    "booking_request": ("New booking request", "A customer has sent a booking request."),
    "booking_accepted": ("Booking accepted", "Your host accepted the booking request."),
    "booking_declined": ("Booking declined", "The host declined the booking request."),
    "booking_cancelled": ("Booking cancelled", "A booking has been cancelled."),
    "booking_confirmed": ("Booking confirmed", "Your booking is confirmed."),
    "payment_failed": ("Payment not completed", "The payment could not be completed."),
    "payment_succeeded": ("Payment received", "Your booking payment was received."),
    "payment_refunded": ("Refund processed", "A refund has been processed for your booking."),
    "upcoming_booking": ("Upcoming booking reminder", "Your confirmed booking is coming up within 24 hours."),
    "new_message": ("New booking message", "You have a new message about a booking."),
    "verification_status": ("Verification update", "Your verification status has been updated."),
    "application_status": ("Host application update", "Your host application status has changed."),
    "review_received": ("New review", "A customer left a review after a completed booking."),
}


def enqueue_email(recipient, event_type, aggregate_type, aggregate_id, payload=None, key=None):
    if event_type not in EMAIL_CONTENT:
        raise ValueError(f"Unsupported email event type: {event_type}")
    event_key = key or f"{event_type}:{aggregate_type}:{aggregate_id}:{recipient.pk}"
    event, created = TransactionalOutbox.objects.get_or_create(
        idempotency_key=event_key,
        defaults={
            "recipient": recipient,
            "event_type": event_type,
            "aggregate_type": aggregate_type,
            "aggregate_id": str(aggregate_id),
            "payload": payload or {},
        },
    )
    if not created and (
        event.recipient_id != recipient.pk
        or event.event_type != event_type
        or event.aggregate_type != aggregate_type
        or event.aggregate_id != str(aggregate_id)
        or event.payload != (payload or {})
    ):
        raise ValueError("An outbox idempotency key was reused for a different notification.")
    if created:
        transaction.on_commit(
            lambda event_id=str(event.pk): _dispatch_outbox_event(event_id),
            robust=True,
        )
    return event


def _dispatch_outbox_event(event_id):
    from .tasks import deliver_outbox_event

    try:
        deliver_outbox_event.delay(event_id)
    except Exception:
        logger.exception("Could not dispatch transactional outbox event %s", event_id)
