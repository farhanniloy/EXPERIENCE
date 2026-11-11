from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import Booking, BookingEvent, Experience, HostProfile, VerificationCheck


ALLOWED_BOOKING_TRANSITIONS = {
    Booking.Status.REQUESTED: {Booking.Status.DECLINED, Booking.Status.AWAITING_PAYMENT},
    Booking.Status.AWAITING_PAYMENT: {
        Booking.Status.CONFIRMED,
        Booking.Status.EXPIRED,
        Booking.Status.CANCELLED,
    },
    Booking.Status.CONFIRMED: {Booking.Status.CANCELLED, Booking.Status.IN_PROGRESS},
    Booking.Status.IN_PROGRESS: {Booking.Status.COMPLETED, Booking.Status.DISPUTED},
}


@transaction.atomic
def transition_booking(booking_id, next_status, actor=None, metadata=None):
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    if next_status not in ALLOWED_BOOKING_TRANSITIONS.get(booking.status, set()):
        raise ValidationError(f"Booking cannot transition from {booking.status} to {next_status}.")

    previous_status = booking.status
    booking.status = next_status
    booking.save(update_fields=["status", "updated_at"])
    BookingEvent.objects.create(
        booking=booking,
        actor=actor,
        event_type="status_changed",
        previous_state=previous_status,
        new_state=next_status,
        metadata=metadata or {},
    )
    return booking


def create_booking(
    *,
    customer,
    host,
    experience,
    start_at,
    end_at,
    idempotency_key,
    timezone_name,
    booking_mode,
    public_venue_name,
    customer_note="",
):
    if end_at <= start_at:
        raise ValidationError("The booking end must be after its start.")
    if timezone.is_naive(start_at) or timezone.is_naive(end_at):
        raise ValidationError("Booking times must include a timezone.")
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError("The booking timezone is invalid.") from exc
    if experience.host_id != host.pk:
        raise ValidationError("The experience does not belong to this host.")
    if host.status != HostProfile.Status.APPROVED:
        raise ValidationError("Only approved hosts can receive bookings.")
    if experience.status != Experience.Status.PUBLISHED:
        raise ValidationError("Only published experiences can be booked.")
    if booking_mode not in {"request", "instant"}:
        raise ValidationError("Booking mode must be request or instant.")
    if not public_venue_name.strip():
        raise ValidationError("Bookings must use a public venue.")
    if booking_mode == "instant" and not experience.instant_booking_enabled:
        raise ValidationError("This experience requires a booking request.")
    if not VerificationCheck.objects.filter(
        user=customer,
        check_type=VerificationCheck.CheckType.AGE,
        status=VerificationCheck.Status.APPROVED,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).exists():
        raise ValidationError("Age verification is required to book.")

    with transaction.atomic():
        existing = Booking.objects.filter(customer=customer, idempotency_key=idempotency_key).first()
        if existing:
            return existing
        HostProfile.objects.select_for_update().get(pk=host.pk)
        status = (
            Booking.Status.AWAITING_PAYMENT
            if booking_mode == "instant"
            else Booking.Status.REQUESTED
        )
        payment_deadline = (
            timezone.now() + timedelta(minutes=getattr(settings, "BOOKING_HOLD_MINUTES", 15))
            if booking_mode == "instant"
            else None
        )
        try:
            with transaction.atomic():
                booking = Booking.objects.create(
                    customer=customer,
                    host=host,
                    experience=experience,
                    start_at=start_at,
                    end_at=end_at,
                    timezone=timezone_name,
                    status=status,
                    currency=experience.currency,
                    base_price_minor=experience.price_minor,
                    total_minor=experience.price_minor,
                    payment_deadline=payment_deadline,
                    public_venue_name=public_venue_name.strip(),
                    customer_note=customer_note,
                    idempotency_key=idempotency_key,
                    snapshot={
                        "title": experience.title,
                        "duration_minutes": int((end_at - start_at).total_seconds() // 60),
                        "base_price_minor": experience.price_minor,
                        "fee_minor": 0,
                        "tax_minor": 0,
                        "currency": experience.currency,
                        "cancellation_policy": experience.cancellation_policy,
                        "booking_mode": booking_mode,
                        "public_venue_name": public_venue_name.strip(),
                        "start_at": start_at.isoformat(),
                        "end_at": end_at.isoformat(),
                    },
                )
        except IntegrityError:
            duplicate = Booking.objects.filter(customer=customer, idempotency_key=idempotency_key).first()
            if duplicate:
                return duplicate
            raise
        BookingEvent.objects.create(
            booking=booking,
            actor=customer,
            event_type="created",
            new_state=booking.status,
            metadata={"booking_mode": booking_mode},
        )
        return booking
