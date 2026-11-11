from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiParameter, extend_schema

from .availability import get_available_slots, parse_date
from .host_views import WriteThrottledAPIView, get_host_profile
from .models import (
    AvailabilityException,
    AvailabilityRule,
    Booking,
    BookingEvent,
    Experience,
    HostProfile,
)
from .services import BookingSlotUnavailable, accept_booking, create_booking, transition_booking


class BookingConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This time is no longer available."
    default_code = "booking_conflict"


class AvailabilityPreferencesSerializer(serializers.Serializer):
    minimum_notice_hours = serializers.IntegerField(min_value=0, max_value=720, required=False)
    max_advance_days = serializers.IntegerField(min_value=1, max_value=365, required=False)
    buffer_minutes = serializers.IntegerField(min_value=0, max_value=1440, required=False)


class AvailabilityRuleSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    weekday = serializers.IntegerField(min_value=0, max_value=6)
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    timezone = serializers.CharField(max_length=64)
    is_active = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        start_time = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError({"end_time": "End time must be later than start time."})
        from .availability import parse_timezone

        parse_timezone(attrs.get("timezone", getattr(self.instance, "timezone", None)))
        return attrs


class AvailabilityExceptionSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()
    exception_type = serializers.ChoiceField(choices=AvailabilityException.ExceptionType.choices)
    notes = serializers.CharField(max_length=250, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["end_at"] <= attrs["start_at"]:
            raise serializers.ValidationError({"end_at": "End time must be later than start time."})
        for field in ("start_at", "end_at"):
            parsed = parse_datetime(str(self.initial_data.get(field, "")))
            if parsed is None or timezone.is_naive(parsed):
                raise serializers.ValidationError({field: "Include a timezone offset."})
        return attrs


class AvailabilitySlotSerializer(serializers.Serializer):
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()
    timezone = serializers.CharField()


class AvailabilityOverviewSerializer(serializers.Serializer):
    preferences = AvailabilityPreferencesSerializer()
    rules = AvailabilityRuleSerializer(many=True)
    exceptions = AvailabilityExceptionSerializer(many=True)


class BookingCreateSerializer(serializers.Serializer):
    experience_id = serializers.UUIDField()
    start_at = serializers.DateTimeField()
    duration_minutes = serializers.IntegerField(min_value=15, max_value=1440)
    booking_mode = serializers.ChoiceField(choices=["request", "instant"])
    timezone = serializers.CharField(max_length=64)
    public_venue_name = serializers.CharField(max_length=180)
    customer_note = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate_start_at(self, value):
        parsed = parse_datetime(str(self.initial_data.get("start_at", "")))
        if parsed is None or timezone.is_naive(parsed):
            raise serializers.ValidationError("Include a timezone offset.")
        return value


class BookingActionRequestSerializer(serializers.Serializer):
    pass


class BookingOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()
    timezone = serializers.CharField()
    experience_title = serializers.CharField()
    other_party = serializers.CharField()
    viewer_role = serializers.ChoiceField(choices=["customer", "host"])
    public_venue_name = serializers.CharField()
    customer_note = serializers.CharField()
    total_minor = serializers.IntegerField()
    currency = serializers.CharField()
    payment_deadline = serializers.DateTimeField(allow_null=True)


class BookingEventOutputSerializer(serializers.Serializer):
    event_type = serializers.CharField()
    previous_state = serializers.CharField()
    new_state = serializers.CharField()
    created_at = serializers.DateTimeField()


def _serialize_booking(booking, user):
    host_view = booking.host.user_id == user.pk
    other_party_account = (
        getattr(booking.customer, "along_account", None)
        if host_view
        else booking.host.user.along_account
    )
    snapshot_name = booking.snapshot.get("customer_name" if host_view else "host_name")
    return {
        "id": booking.id,
        "status": booking.status,
        "start_at": booking.start_at,
        "end_at": booking.end_at,
        "timezone": booking.timezone,
        "experience_title": booking.snapshot.get("title", booking.experience.title),
        "other_party": snapshot_name or (other_party_account.display_name if other_party_account else "Customer"),
        "viewer_role": "host" if host_view else "customer",
        "public_venue_name": booking.public_venue_name,
        "customer_note": booking.customer_note,
        "total_minor": booking.total_minor,
        "currency": booking.currency,
        "payment_deadline": booking.payment_deadline,
    }


def _booking_queryset():
    return Booking.objects.select_related(
        "experience",
        "host__user__along_account",
        "customer__along_account",
    )


class PublicExperienceAvailabilityView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "default"

    @extend_schema(responses=AvailabilitySlotSerializer(many=True))
    def get(self, request, experience_slug):
        experience = get_object_or_404(
            Experience.objects.select_related("host"),
            slug=experience_slug,
            status=Experience.Status.PUBLISHED,
            host__status=HostProfile.Status.APPROVED,
            host__user__along_account__status="active",
        )
        start_day = parse_date(request.query_params.get("from"), "from")
        end_day = parse_date(request.query_params.get("to", request.query_params.get("from")), "to")
        try:
            duration_minutes = int(request.query_params.get("duration_minutes", experience.duration_minutes))
        except (TypeError, ValueError) as exc:
            raise ValidationError({"duration_minutes": "Use a whole number of minutes."}) from exc
        timezone_name = request.query_params.get("timezone", settings.TIME_ZONE)
        slots = get_available_slots(
            experience.host,
            experience,
            start_day,
            end_day,
            timezone_name,
            duration_minutes,
        )
        return Response(slots)


class MyAvailabilityView(WriteThrottledAPIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "host_onboarding"

    @extend_schema(responses=AvailabilityOverviewSerializer)
    def get(self, request):
        _, host = get_host_profile(request.user)
        return Response({
            "preferences": {
                "minimum_notice_hours": host.minimum_notice_hours,
                "max_advance_days": host.max_advance_days,
                "buffer_minutes": host.buffer_minutes,
            },
            "rules": list(host.availability_rules.order_by("weekday", "start_time").values(
                "id", "weekday", "start_time", "end_time", "timezone", "is_active"
            )),
            "exceptions": list(host.availability_exceptions.order_by("-start_at").values(
                "id", "start_at", "end_at", "exception_type", "notes"
            )[:100]),
        })


class MyAvailabilityPreferencesView(WriteThrottledAPIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "host_onboarding"

    @extend_schema(request=AvailabilityPreferencesSerializer, responses=AvailabilityPreferencesSerializer)
    def patch(self, request):
        _, host = get_host_profile(request.user)
        serializer = AvailabilityPreferencesSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(host, field, value)
        host.save(update_fields=[*serializer.validated_data.keys(), "updated_at"])
        return Response(serializer.data)


class MyAvailabilityRulesView(WriteThrottledAPIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "host_onboarding"

    @extend_schema(request=AvailabilityRuleSerializer, responses={"201": AvailabilityRuleSerializer})
    def post(self, request):
        _, host = get_host_profile(request.user)
        serializer = AvailabilityRuleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule = AvailabilityRule.objects.create(host=host, **serializer.validated_data)
        return Response(AvailabilityRuleSerializer(rule).data, status=status.HTTP_201_CREATED)


class MyAvailabilityRuleDetailView(WriteThrottledAPIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "host_onboarding"

    def get_rule(self, request, rule_id):
        _, host = get_host_profile(request.user)
        return get_object_or_404(AvailabilityRule, pk=rule_id, host=host)

    @extend_schema(request=AvailabilityRuleSerializer, responses={"200": AvailabilityRuleSerializer})
    def patch(self, request, rule_id):
        rule = self.get_rule(request, rule_id)
        serializer = AvailabilityRuleSerializer(rule, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(rule, field, value)
        rule.save()
        return Response(AvailabilityRuleSerializer(rule).data)

    @extend_schema(responses={"204": None})
    def delete(self, request, rule_id):
        self.get_rule(request, rule_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyAvailabilityExceptionsView(WriteThrottledAPIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "host_onboarding"

    @extend_schema(request=AvailabilityExceptionSerializer, responses={"201": AvailabilityExceptionSerializer})
    def post(self, request):
        _, host = get_host_profile(request.user)
        serializer = AvailabilityExceptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        exception = AvailabilityException.objects.create(host=host, **serializer.validated_data)
        return Response(AvailabilityExceptionSerializer(exception).data, status=status.HTTP_201_CREATED)


class MyAvailabilityExceptionDetailView(WriteThrottledAPIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "host_onboarding"

    def get_exception(self, request, exception_id):
        _, host = get_host_profile(request.user)
        return get_object_or_404(AvailabilityException, pk=exception_id, host=host)

    @extend_schema(responses={"204": None})
    def delete(self, request, exception_id):
        self.get_exception(request, exception_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BookingListCreateView(WriteThrottledAPIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "booking"

    @extend_schema(responses={"200": BookingOutputSerializer(many=True)})
    def get(self, request):
        bookings = _booking_queryset().filter(
            Q(customer=request.user) | Q(host__user=request.user)
        ).order_by("-start_at")[:100]
        return Response([_serialize_booking(booking, request.user) for booking in bookings])

    @extend_schema(
        parameters=[OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=True)],
        request=BookingCreateSerializer,
        responses={"201": BookingOutputSerializer},
        operation_id="bookings_create",
    )
    def post(self, request):
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key:
            raise ValidationError({"Idempotency-Key": "This header is required."})
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        experience = get_object_or_404(
            Experience.objects.select_related("host"),
            pk=values["experience_id"],
            status=Experience.Status.PUBLISHED,
            host__status=HostProfile.Status.APPROVED,
        )
        start_at = values["start_at"]
        end_at = start_at + timedelta(minutes=values["duration_minutes"])
        try:
            booking = create_booking(
                customer=request.user,
                host=experience.host,
                experience=experience,
                start_at=start_at,
                end_at=end_at,
                idempotency_key=idempotency_key,
                timezone_name=values["timezone"],
                booking_mode=values["booking_mode"],
                public_venue_name=values["public_venue_name"],
                customer_note=values.get("customer_note", ""),
            )
        except BookingSlotUnavailable as exc:
            raise BookingConflict() from exc
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        except IntegrityError as exc:
            raise BookingConflict() from exc
        booking = _booking_queryset().get(pk=booking.pk)
        return Response(_serialize_booking(booking, request.user), status=status.HTTP_201_CREATED)


class BookingDetailView(WriteThrottledAPIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "booking"

    def get_booking(self, request, booking_id):
        return get_object_or_404(
            _booking_queryset().filter(Q(customer=request.user) | Q(host__user=request.user)),
            pk=booking_id,
        )

    @extend_schema(request=None, responses=BookingOutputSerializer, operation_id="booking_action")
    def get(self, request, booking_id):
        return Response(_serialize_booking(self.get_booking(request, booking_id), request.user))


class BookingActionView(WriteThrottledAPIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "booking"
    serializer_class = BookingActionRequestSerializer

    @extend_schema(responses=BookingOutputSerializer)
    def post(self, request, booking_id, action):
        booking = get_object_or_404(
            _booking_queryset().filter(Q(customer=request.user) | Q(host__user=request.user)),
            pk=booking_id,
        )
        is_host = booking.host.user_id == request.user.pk
        if action in {"accept", "decline", "start", "complete"} and not is_host:
            raise PermissionDenied("Only the host can perform this action.")
        if action == "accept":
            try:
                booking = accept_booking(booking_id, request.user)
            except BookingSlotUnavailable as exc:
                raise BookingConflict() from exc
            except DjangoValidationError as exc:
                raise ValidationError(exc.messages) from exc
            except IntegrityError as exc:
                raise BookingConflict() from exc
        elif action == "decline":
            if booking.status != Booking.Status.REQUESTED:
                raise ValidationError("Only requested bookings can be declined.")
            booking = _transition(booking_id, Booking.Status.DECLINED, request.user)
        elif action == "cancel":
            if booking.status not in {
                Booking.Status.REQUESTED,
                Booking.Status.AWAITING_PAYMENT,
                Booking.Status.CONFIRMED,
            }:
                raise ValidationError("This booking can no longer be cancelled.")
            booking = _transition(booking_id, Booking.Status.CANCELLED, request.user)
        elif action == "start":
            booking = _transition(booking_id, Booking.Status.IN_PROGRESS, request.user)
        elif action == "complete":
            booking = _transition(booking_id, Booking.Status.COMPLETED, request.user)
        else:
            raise ValidationError({"action": "Choose accept, decline, cancel, start, or complete."})
        return Response(_serialize_booking(_booking_queryset().get(pk=booking.pk), request.user))


class BookingEventListView(WriteThrottledAPIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "booking"

    @extend_schema(responses=BookingEventOutputSerializer(many=True))
    def get(self, request, booking_id):
        get_object_or_404(
            Booking.objects.filter(Q(customer=request.user) | Q(host__user=request.user)),
            pk=booking_id,
        )
        events = BookingEvent.objects.filter(booking_id=booking_id).order_by("created_at")
        return Response([
            {
                "event_type": event.event_type,
                "previous_state": event.previous_state,
                "new_state": event.new_state,
                "created_at": event.created_at,
            }
            for event in events
        ])


def _transition(booking_id, next_status, actor):
    try:
        return transition_booking(booking_id, next_status, actor)
    except DjangoValidationError as exc:
        raise ValidationError(exc.messages) from exc
