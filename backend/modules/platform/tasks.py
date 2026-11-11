from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import Booking, BookingEvent


@shared_task
def expire_booking_hold(booking_id):
    with transaction.atomic():
        booking = Booking.objects.select_for_update().filter(pk=booking_id).first()
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
        return True
