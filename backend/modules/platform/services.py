import hashlib
import json
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
    Block,
    Conversation,
    Experience,
    EventCollection,
    HostProfile,
    ModerationQueueItem,
    User,
    VerificationCheck,
)
from .audit import record_admin_action
from .availability import is_slot_available
from .moderation import flag_experience, queue_listing_review
from .notifications import enqueue_email


class BookingSlotUnavailable(ValidationError):
    pass


ALLOWED_BOOKING_TRANSITIONS = {
    Booking.Status.REQUESTED: {
        Booking.Status.DECLINED,
        Booking.Status.AWAITING_PAYMENT,
        Booking.Status.CANCELLED,
    },
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
    if item.message_id:
        item.message.moderation_status = (
            item.message.ModerationStatus.VISIBLE
            if action == "approve"
            else item.message.ModerationStatus.REMOVED
        )
        item.message.flagged = action == "reject"
        item.message.save(update_fields=["moderation_status", "flagged"])
        item.status = (
            ModerationQueueItem.Status.APPROVED
            if action == "approve"
            else ModerationQueueItem.Status.REJECTED
        )
    elif action == "approve":
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
    record_admin_action(
        reviewer,
        f"moderation_{action}",
        item,
        {"queue_type": item.queue_type, "experience_id": str(item.experience_id) if item.experience_id else None},
    )
    return item


def expire_event_collections():
    now = timezone.now()
    return EventCollection.objects.filter(
        status=EventCollection.Status.ACTIVE,
        ends_at__lte=now,
    ).update(status=EventCollection.Status.INACTIVE, updated_at=now)


@transaction.atomic
def transition_booking(booking_id, next_status, actor=None, metadata=None):
    booking = Booking.objects.select_for_update().select_related(
        "customer", "host__user", "experience"
    ).get(pk=booking_id)
    if next_status not in ALLOWED_BOOKING_TRANSITIONS.get(booking.status, set()):
        raise ValidationError(f"Booking cannot transition from {booking.status} to {next_status}.")

    previous_status = booking.status
    booking.status = next_status
    update_fields = ["status", "updated_at"]
    if next_status in {Booking.Status.CANCELLED, Booking.Status.EXPIRED, Booking.Status.DECLINED}:
        booking.payment_deadline = None
        update_fields.append("payment_deadline")
    booking.save(update_fields=update_fields)
    BookingEvent.objects.create(
        booking=booking,
        actor=actor,
        event_type="status_changed",
        previous_state=previous_status,
        new_state=next_status,
        metadata=metadata or {},
    )
    if next_status in {Booking.Status.CONFIRMED, Booking.Status.CANCELLED, Booking.Status.DECLINED}:
        event_type = {
            Booking.Status.CONFIRMED: "booking_confirmed",
            Booking.Status.CANCELLED: "booking_cancelled",
            Booking.Status.DECLINED: "booking_declined",
        }[next_status]
        for recipient in (booking.customer, booking.host.user):
            enqueue_email(
                recipient,
                event_type,
                "booking",
                booking.pk,
                {"title": booking.snapshot.get("title", booking.experience.title)},
            )
    return booking


def _schedule_hold_expiry(booking):
    from .tasks import expire_booking_hold

    delay = max(0, int((booking.payment_deadline - timezone.now()).total_seconds()))
    transaction.on_commit(
        lambda: expire_booking_hold.apply_async(args=[str(booking.pk)], countdown=delay)
    )


def _expire_due_holds(host):
    now = timezone.now()
    due_holds = Booking.objects.select_for_update().select_related(
        "customer", "host__user", "experience"
    ).filter(
        host=host,
        status=Booking.Status.AWAITING_PAYMENT,
        payment_deadline__lte=now,
    )
    for booking in due_holds:
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
        for recipient in (booking.customer, booking.host.user):
            enqueue_email(
                recipient,
                "payment_failed",
                "booking",
                booking.pk,
                {"title": booking.snapshot.get("title", booking.experience.title)},
            )
        for recipient in (booking.customer, booking.host.user):
            enqueue_email(
                recipient,
                "payment_failed",
                "booking",
                booking.pk,
                {"title": booking.snapshot.get("title", booking.experience.title)},
            )


@transaction.atomic
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
    if not idempotency_key or len(idempotency_key) > 128:
        raise ValidationError("A valid idempotency key is required.")
    if end_at <= start_at:
        raise ValidationError("The booking end must be after its start.")
    if start_at <= timezone.now():
        raise ValidationError("Bookings must start in the future.")
    if timezone.is_naive(start_at) or timezone.is_naive(end_at):
        raise ValidationError("Booking times must include a timezone.")
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError("The booking timezone is invalid.") from exc
    if experience.host_id != host.pk:
        raise ValidationError("The experience does not belong to this host.")
    if host.user_id == customer.pk:
        raise ValidationError("Hosts cannot book their own experiences.")
    if Block.objects.filter(
        Q(blocker_id=customer.pk, blocked_id=host.user_id)
        | Q(blocker_id=host.user_id, blocked_id=customer.pk)
    ).exists():
        raise ValidationError("This host is unavailable for booking.")
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

    duration_minutes = int((end_at - start_at).total_seconds() // 60)
    request_data = {
        "experience_id": str(experience.pk),
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat(),
        "timezone": timezone_name,
        "booking_mode": booking_mode,
        "public_venue_name": public_venue_name.strip(),
        "customer_note": customer_note,
    }
    request_fingerprint = hashlib.sha256(
        json.dumps(request_data, sort_keys=True).encode("utf-8")
    ).hexdigest()
    existing = Booking.objects.filter(customer=customer, idempotency_key=idempotency_key).first()
    if existing:
        if existing.snapshot.get("request_fingerprint") != request_fingerprint:
            raise ValidationError("This idempotency key was already used for a different booking request.")
        return existing

    locked_host = HostProfile.objects.select_for_update().get(pk=host.pk)
    _expire_due_holds(locked_host)
    locked_experience = Experience.objects.select_for_update().get(pk=experience.pk)
    if (
        locked_host.status != HostProfile.Status.APPROVED
        or not User.objects.filter(auth_user=locked_host.user_id, status=User.Status.ACTIVE).exists()
    ):
        raise ValidationError("Only approved hosts can receive bookings.")
    if locked_experience.host_id != locked_host.pk or locked_experience.status != Experience.Status.PUBLISHED:
        raise ValidationError("This experience is no longer available for booking.")
    if not User.objects.filter(auth_user=customer, status=User.Status.ACTIVE).exists():
        raise ValidationError("This account cannot create bookings.")
    if Block.objects.filter(
        Q(blocker_id=customer.pk, blocked_id=locked_host.user_id)
        | Q(blocker_id=locked_host.user_id, blocked_id=customer.pk)
    ).exists():
        raise ValidationError("This host is unavailable for booking.")
    if not is_slot_available(
        locked_host,
        locked_experience,
        start_at,
        duration_minutes,
        timezone_name,
    ):
        raise BookingSlotUnavailable("This time is no longer available.")

    booking_status = (
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
                host=locked_host,
                experience=locked_experience,
                start_at=start_at,
                end_at=end_at,
                timezone=timezone_name,
                status=booking_status,
                currency=locked_experience.currency,
                base_price_minor=locked_experience.price_minor,
                total_minor=locked_experience.price_minor,
                payment_deadline=payment_deadline,
                public_venue_name=public_venue_name.strip(),
                customer_note=customer_note,
                idempotency_key=idempotency_key,
                snapshot={
                    "title": locked_experience.title,
                    "host_name": locked_host.user.along_account.display_name,
                    "customer_name": getattr(getattr(customer, "along_account", None), "display_name", ""),
                    "duration_minutes": duration_minutes,
                    "base_price_minor": locked_experience.price_minor,
                    "fee_minor": 0,
                    "tax_minor": 0,
                    "currency": locked_experience.currency,
                    "cancellation_policy": locked_experience.cancellation_policy,
                    "booking_mode": booking_mode,
                    "public_venue_name": public_venue_name.strip(),
                    "meeting_arrangement": {"type": "public_venue", "name": public_venue_name.strip()},
                    "start_at": start_at.isoformat(),
                    "end_at": end_at.isoformat(),
                    "request_fingerprint": request_fingerprint,
                },
            )
    except IntegrityError:
        duplicate = Booking.objects.filter(customer=customer, idempotency_key=idempotency_key).first()
        if duplicate:
            if duplicate.snapshot.get("request_fingerprint") != request_fingerprint:
                raise ValidationError("This idempotency key was already used for a different booking request.")
            return duplicate
        raise
    BookingEvent.objects.create(
        booking=booking,
        actor=customer,
        event_type="created",
        new_state=booking.status,
        metadata={"booking_mode": booking_mode},
    )
    Conversation.objects.get_or_create(booking=booking)
    enqueue_email(
        locked_host.user,
        "booking_request",
        "booking",
        booking.pk,
        {"title": locked_experience.title},
    )
    if payment_deadline:
        _schedule_hold_expiry(booking)
    return booking


@transaction.atomic
def accept_booking(booking_id, actor):
    booking_ref = Booking.objects.select_related("host").get(pk=booking_id)
    locked_host = HostProfile.objects.select_for_update().get(pk=booking_ref.host_id)
    _expire_due_holds(locked_host)
    locked_experience = Experience.objects.select_for_update().get(pk=booking_ref.experience_id)
    booking = Booking.objects.select_for_update().select_related("experience").get(pk=booking_id)
    if booking.status != Booking.Status.REQUESTED:
        raise ValidationError(f"Booking cannot be accepted from {booking.status}.")
    if (
        locked_host.status != HostProfile.Status.APPROVED
        or locked_experience.status != Experience.Status.PUBLISHED
        or not User.objects.filter(auth_user=locked_host.user_id, status=User.Status.ACTIVE).exists()
    ):
        raise ValidationError("This experience is no longer available for booking.")
    if not is_slot_available(
        booking.host,
        booking.experience,
        booking.start_at,
        int((booking.end_at - booking.start_at).total_seconds() // 60),
        booking.timezone,
        exclude_booking_id=booking.pk,
    ):
        raise BookingSlotUnavailable("This time is no longer available.")
    booking.payment_deadline = timezone.now() + timedelta(
        minutes=getattr(settings, "BOOKING_HOLD_MINUTES", 15)
    )
    booking.save(update_fields=["payment_deadline", "updated_at"])
    booking = transition_booking(booking.pk, Booking.Status.AWAITING_PAYMENT, actor=actor)
    enqueue_email(
        booking.customer,
        "booking_accepted",
        "booking",
        booking.pk,
        {"title": booking.snapshot.get("title", booking.experience.title)},
    )
    _schedule_hold_expiry(booking)
    return booking
