from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied as APIPermissionDenied
from rest_framework.exceptions import ValidationError as APIValidationError

from .models import (
    Booking,
    BookingEvent,
    Experience,
    HostProfile,
    ModerationQueueItem,
    VerificationCheck,
)
from .moderation import flag_experience, queue_listing_review


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


def submit_experience_for_publication(host, experience, submit_for_review):
    flagged = flag_experience(experience)
    if host.status != HostProfile.Status.APPROVED:
        if submit_for_review:
            raise APIPermissionDenied(
                "Host approval is required before submitting an experience for publishing."
            )
        if flagged:
            queue_listing_review(host, experience, False, flagged)
        else:
            queue_listing_review(host, experience, False, {})
        experience.status = Experience.Status.DRAFT
        return
    is_first_listing = submit_for_review and not host.first_listing_approved
    if flagged or is_first_listing:
        experience.status = Experience.Status.PENDING_REVIEW
        queue_listing_review(host, experience, is_first_listing, flagged)
    elif submit_for_review:
        queue_listing_review(host, experience, False, {})
        experience.status = Experience.Status.PUBLISHED
    elif experience.status == Experience.Status.PENDING_REVIEW and not host.first_listing_approved:
        experience.status = Experience.Status.PENDING_REVIEW
        queue_listing_review(host, experience, True, {})
    elif experience.status == Experience.Status.PENDING_REVIEW:
        queue_listing_review(host, experience, False, {})
        experience.status = Experience.Status.DRAFT


@transaction.atomic
def deactivate_experience(experience):
    experience.status = Experience.Status.INACTIVE
    experience.save(update_fields=["status", "updated_at"])
    ModerationQueueItem.objects.filter(
        experience=experience, status=ModerationQueueItem.Status.PENDING
    ).update(status=ModerationQueueItem.Status.CLEARED, updated_at=timezone.now())


def apply_moderation_decision(item, action, reviewer):
    if action not in {"approve", "reject"}:
        raise APIValidationError({"action": "Choose approve or reject."})
    if item.status != ModerationQueueItem.Status.PENDING:
        raise APIValidationError("This moderation item has already been reviewed.")
    if action == "approve":
        if item.experience_id:
            if item.host.status != HostProfile.Status.APPROVED:
                raise APIValidationError("Approve the host application before approving its listing.")
            item.experience.status = Experience.Status.PUBLISHED
            item.experience.save(update_fields=["status", "updated_at"])
            item.host.first_listing_approved = True
            item.host.save(update_fields=["first_listing_approved", "updated_at"])
        elif item.queue_type in {
            ModerationQueueItem.QueueType.HOST_APPLICATION,
            ModerationQueueItem.QueueType.PROFILE_CONTENT,
        }:
            item.host.status = HostProfile.Status.APPROVED
            item.host.save(update_fields=["status", "updated_at"])
        item.status = ModerationQueueItem.Status.APPROVED
    else:
        if item.experience_id:
            item.experience.status = Experience.Status.INACTIVE
            item.experience.save(update_fields=["status", "updated_at"])
        else:
            item.host.status = HostProfile.Status.REJECTED
            item.host.save(update_fields=["status", "updated_at"])
        item.status = ModerationQueueItem.Status.REJECTED
    item.reviewed_by = reviewer
    item.reviewed_at = timezone.now()
    item.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
    return item


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
