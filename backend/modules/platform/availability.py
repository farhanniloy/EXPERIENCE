from datetime import date, datetime, time, timedelta, timezone as datetime_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import AvailabilityException, AvailabilityRule, Booking

SLOT_INTERVAL_MINUTES = 30


def parse_timezone(value):
    try:
        return ZoneInfo(value)
    except (ZoneInfoNotFoundError, TypeError) as exc:
        raise ValidationError({"timezone": "Choose a valid IANA timezone."}) from exc


def parse_date(value, field):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({field: "Use a date in YYYY-MM-DD format."}) from exc


def _local_datetime(day, clock_time, zone):
    candidate = datetime.combine(day, clock_time, tzinfo=zone)
    if candidate.astimezone(datetime_timezone.utc).astimezone(zone).replace(tzinfo=None) != candidate.replace(tzinfo=None):
        return None
    return candidate


def _weekly_intervals(host, start_at, end_at):
    intervals = []
    rules = host.availability_rules.filter(is_active=True)
    for rule in rules:
        zone = parse_timezone(rule.timezone)
        local_start = start_at.astimezone(zone).date() - timedelta(days=1)
        local_end = end_at.astimezone(zone).date() + timedelta(days=1)
        while local_start <= local_end:
            if local_start.weekday() == rule.weekday:
                start = _local_datetime(local_start, rule.start_time, zone)
                end = _local_datetime(local_start, rule.end_time, zone)
                if start and end and end > start:
                    intervals.append((start.astimezone(datetime_timezone.utc), end.astimezone(datetime_timezone.utc)))
            local_start += timedelta(days=1)
    return intervals


def _available_intervals(host, start_at, end_at):
    intervals = _weekly_intervals(host, start_at, end_at)
    for exception in host.availability_exceptions.filter(
        exception_type=AvailabilityException.ExceptionType.AVAILABLE,
        start_at__lt=end_at,
        end_at__gt=start_at,
    ):
        intervals.append((exception.start_at, exception.end_at))
    return intervals


def _candidate_is_available(
    host,
    start_at,
    end_at,
    now=None,
    exclude_booking_id=None,
    unavailable=None,
    reservations=None,
    intervals=None,
):
    now = now or timezone.now()
    if start_at < now + timedelta(hours=host.minimum_notice_hours):
        return False
    if start_at > now + timedelta(days=host.max_advance_days):
        return False

    if intervals is None:
        intervals = _available_intervals(host, start_at, end_at)
    if not any(start_at >= interval_start and end_at <= interval_end for interval_start, interval_end in intervals):
        return False

    if unavailable is None:
        unavailable = host.availability_exceptions.filter(
            exception_type=AvailabilityException.ExceptionType.UNAVAILABLE,
            start_at__lt=end_at,
            end_at__gt=start_at,
        ).values_list("start_at", "end_at")
    if any(start_at < blocked_end and end_at > blocked_start for blocked_start, blocked_end in unavailable):
        return False

    buffered_start = start_at - timedelta(minutes=host.buffer_minutes)
    buffered_end = end_at + timedelta(minutes=host.buffer_minutes)
    if reservations is None:
        reservations = Booking.objects.filter(
            host=host,
            start_at__lt=buffered_end,
            end_at__gt=buffered_start,
        ).filter(
            Q(status__in=[Booking.Status.CONFIRMED, Booking.Status.IN_PROGRESS])
            | Q(status=Booking.Status.AWAITING_PAYMENT, payment_deadline__gt=now)
        )
        if exclude_booking_id:
            reservations = reservations.exclude(pk=exclude_booking_id)
        return not reservations.exists()
    return not any(
        booking_id != exclude_booking_id
        and start_at < booking_end + timedelta(minutes=host.buffer_minutes)
        and end_at + timedelta(minutes=host.buffer_minutes) > booking_start
        for booking_id, booking_start, booking_end in reservations
    )


def get_available_slots(host, experience, start_day, end_day, timezone_name, duration_minutes, now=None):
    display_zone = parse_timezone(timezone_name)
    if end_day < start_day:
        raise ValidationError({"to": "The end date must be on or after the start date."})
    if (end_day - start_day).days > 30:
        raise ValidationError({"to": "Request no more than 31 calendar days at a time."})
    minimum_duration = experience.min_duration_minutes or experience.duration_minutes
    maximum_duration = experience.max_duration_minutes or experience.duration_minutes
    if duration_minutes < minimum_duration or duration_minutes > maximum_duration:
        raise ValidationError({"duration_minutes": "Choose a duration within this experience's limits."})

    window_start = datetime.combine(start_day, time.min, tzinfo=display_zone).astimezone(datetime_timezone.utc)
    window_end = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=display_zone).astimezone(datetime_timezone.utc)
    intervals = _available_intervals(host, window_start, window_end)
    reservation_start = window_start - timedelta(minutes=host.buffer_minutes)
    reservation_end = window_end + timedelta(minutes=host.buffer_minutes)
    unavailable = list(host.availability_exceptions.filter(
        exception_type=AvailabilityException.ExceptionType.UNAVAILABLE,
        start_at__lt=window_end,
        end_at__gt=window_start,
    ).values_list("start_at", "end_at"))
    reservations = list(
        Booking.objects.filter(
            host=host,
            start_at__lt=reservation_end,
            end_at__gt=reservation_start,
        ).filter(
            Q(status__in=[Booking.Status.CONFIRMED, Booking.Status.IN_PROGRESS])
            | Q(status=Booking.Status.AWAITING_PAYMENT, payment_deadline__gt=now or timezone.now())
        ).values_list("id", "start_at", "end_at")
    )

    step = timedelta(minutes=SLOT_INTERVAL_MINUTES)
    duration = timedelta(minutes=duration_minutes)
    slots = {}
    for interval_start, interval_end in intervals:
        candidate = interval_start
        while candidate + duration <= interval_end:
            candidate_end = candidate + duration
            if not any(candidate < blocked_end and candidate_end > blocked_start for blocked_start, blocked_end in unavailable):
                if _candidate_is_available(
                    host,
                    candidate,
                    candidate_end,
                    now,
                    unavailable=unavailable,
                    reservations=reservations,
                    intervals=intervals,
                ):
                    if window_start <= candidate < window_end:
                        slots[candidate] = {
                            "start_at": candidate.isoformat(),
                            "end_at": candidate_end.isoformat(),
                            "timezone": timezone_name,
                        }
            candidate += step
    return [slots[start] for start in sorted(slots)]


def is_slot_available(host, experience, start_at, duration_minutes, timezone_name, exclude_booking_id=None):
    display_zone = parse_timezone(timezone_name)
    minimum_duration = experience.min_duration_minutes or experience.duration_minutes
    maximum_duration = experience.max_duration_minutes or experience.duration_minutes
    if duration_minutes < minimum_duration or duration_minutes > maximum_duration:
        return False
    return _candidate_is_available(
        host,
        start_at,
        start_at + timedelta(minutes=duration_minutes),
        exclude_booking_id=exclude_booking_id,
    )
