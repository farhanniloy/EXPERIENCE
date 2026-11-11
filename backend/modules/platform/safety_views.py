from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Booking,
    HostProfile,
    Review,
    SafetyCheckIn,
    SafetyIncident,
    SafetyReport,
)


class SafetyReportCreateSerializer(serializers.Serializer):
    booking_id = serializers.UUIDField(required=False)
    review_id = serializers.UUIDField(required=False)
    reason = serializers.ChoiceField(
        choices=[
            "harassment",
            "safety_concern",
            "no_show",
            "misconduct",
            "impersonation",
            "review_content",
            "other",
        ]
    )
    description = serializers.CharField(max_length=5000, trim_whitespace=True)

    def validate(self, attrs):
        if bool(attrs.get("booking_id")) == bool(attrs.get("review_id")):
            raise serializers.ValidationError("Provide either a booking ID or a review ID.")
        return attrs


class SafetyCheckInSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=SafetyCheckIn.Status.choices)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ReviewCreateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    private_safety_feedback = serializers.CharField(
        max_length=2000, required=False, allow_blank=True, write_only=True
    )


class PublicReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source="reviewer.along_account.display_name")
    verified_booking = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ["id", "reviewer_name", "rating", "comment", "created_at", "verified_booking"]

    def get_verified_booking(self, review) -> bool:
        return review.booking.status == Booking.Status.COMPLETED


class SafetyReportOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    incident_id = serializers.UUIDField()
    status = serializers.CharField()
    review_id = serializers.UUIDField(allow_null=True)


class SafetyCheckInOutputSerializer(serializers.Serializer):
    status = serializers.CharField()
    checked_at = serializers.DateTimeField()
    safety_team_notified = serializers.BooleanField()


class BookingReviewOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    verified_booking = serializers.BooleanField()


def _booking_for_party(booking_id, auth_user):
    booking = get_object_or_404(
        Booking.objects.select_related("host__user", "customer", "experience"),
        pk=booking_id,
    )
    if auth_user.pk not in {booking.customer_id, booking.host.user_id}:
        raise PermissionDenied("Only participants can access this booking's safety tools.")
    return booking


class SafetyReportCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "safety"

    @extend_schema(request=SafetyReportCreateSerializer, responses={201: SafetyReportOutputSerializer})
    def post(self, request):
        serializer = SafetyReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = None
        if serializer.validated_data.get("review_id"):
            review = get_object_or_404(
                Review.objects.select_related("booking__host__user", "reviewer"),
                pk=serializer.validated_data["review_id"],
                status=Review.Status.PUBLISHED,
                booking__status=Booking.Status.COMPLETED,
            )
            if review.reviewer_id == request.user.pk:
                raise ValidationError("You cannot report your own review.")
            booking = review.booking
            reported = review.reviewer
        else:
            booking = _booking_for_party(serializer.validated_data["booking_id"], request.user)
            reported = booking.host.user if request.user.pk == booking.customer_id else booking.customer
        try:
            with transaction.atomic():
                report = SafetyReport.objects.create(
                    reporter=request.user,
                    reported=reported,
                    booking=booking,
                    review=review,
                    reason=serializer.validated_data["reason"],
                    description=serializer.validated_data["description"],
                )
                incident = SafetyIncident.objects.create(report=report, booking=booking)
        except IntegrityError as exc:
            raise ValidationError("Unable to record this safety report.") from exc
        return Response(
            {
                "id": str(report.pk),
                "incident_id": str(incident.pk),
                "status": report.status,
                "review_id": str(review.pk) if review else None,
            },
            status=status.HTTP_201_CREATED,
        )


class SafetyCheckInView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "safety"

    @extend_schema(request=SafetyCheckInSerializer, responses=SafetyCheckInOutputSerializer)
    def post(self, request, booking_id):
        booking = _booking_for_party(booking_id, request.user)
        if booking.status not in {Booking.Status.CONFIRMED, Booking.Status.IN_PROGRESS}:
            raise ValidationError("Safety check-ins are available for confirmed or in-progress bookings.")
        serializer = SafetyCheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            checkin, _ = SafetyCheckIn.objects.update_or_create(
                booking=booking,
                user=request.user,
                defaults=serializer.validated_data,
            )
            incident_created = False
            if checkin.status == SafetyCheckIn.Status.NEEDS_HELP:
                has_open_safety_report = SafetyReport.objects.filter(
                    booking=booking,
                    reporter=request.user,
                    reason="safety_concern",
                    status__in=[SafetyReport.Status.OPEN, SafetyReport.Status.REVIEWING],
                ).exists()
                if not has_open_safety_report:
                    reported = booking.host.user if request.user.pk == booking.customer_id else booking.customer
                    report = SafetyReport.objects.create(
                        reporter=request.user,
                        reported=reported,
                        booking=booking,
                        reason="safety_concern",
                        description=checkin.note or "A booking participant requested safety assistance.",
                    )
                    SafetyIncident.objects.create(report=report, booking=booking)
                    incident_created = True
        return Response(
            {
                "status": checkin.status,
                "checked_at": checkin.updated_at,
                "safety_team_notified": incident_created,
            },
            status=status.HTTP_200_OK,
        )


class BookingReviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "safety"

    @extend_schema(request=ReviewCreateSerializer, responses={201: BookingReviewOutputSerializer})
    def post(self, request, booking_id):
        booking = _booking_for_party(booking_id, request.user)
        if booking.customer_id != request.user.pk:
            raise PermissionDenied("Only the customer can review this booking.")
        if booking.status != Booking.Status.COMPLETED:
            raise ValidationError("Reviews are available only after a completed booking.")
        serializer = ReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if Review.objects.filter(booking=booking, reviewer=request.user).exists():
            raise ValidationError("A review has already been submitted for this booking.")
        try:
            with transaction.atomic():
                review = Review.objects.create(
                    booking=booking,
                    reviewer=request.user,
                    host=booking.host,
                    **serializer.validated_data,
                )
        except IntegrityError as exc:
            raise ValidationError("A review has already been submitted for this booking.") from exc
        return Response(
            {
                "id": str(review.pk),
                "status": review.status,
                "verified_booking": True,
            },
            status=status.HTTP_201_CREATED,
        )


class HostReviewListView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses=PublicReviewSerializer(many=True))
    def get(self, request, host_slug):
        reviews = Review.objects.filter(
            host__slug=host_slug,
            status=Review.Status.PUBLISHED,
            booking__status=Booking.Status.COMPLETED,
            host__status=HostProfile.Status.APPROVED,
            host__user__along_account__status="active",
        ).select_related("reviewer__along_account", "booking").order_by("-created_at")[:100]
        return Response(PublicReviewSerializer(reviews, many=True).data)
