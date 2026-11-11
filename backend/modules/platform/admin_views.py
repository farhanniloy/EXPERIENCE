from django.db import transaction
from django.db.models import Avg
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .audit import record_admin_action
from .notifications import enqueue_email
from .models import (
    AuditLog,
    Booking,
    EventCollection,
    Experience,
    HostProfile,
    PaymentTransaction,
    Review,
    SafetyReport,
    User,
)
from .services import expire_event_collections


class StaffReportActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["review", "resolve", "dismiss", "suspend"])
    resolution_notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class StaffReviewActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])


class AccountSuspensionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[User.Status.ACTIVE, User.Status.SUSPENDED])


class StaffReportOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    reporter = serializers.CharField()
    reported = serializers.CharField()
    booking_id = serializers.UUIDField(allow_null=True)
    review_id = serializers.UUIDField(allow_null=True)
    experience_title = serializers.CharField()
    reason = serializers.CharField()
    description = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    incident_status = serializers.CharField()


class StaffReviewOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    booking_id = serializers.UUIDField()
    experience_title = serializers.CharField()
    reviewer = serializers.CharField()
    host = serializers.CharField()
    rating = serializers.IntegerField()
    comment = serializers.CharField()
    private_safety_feedback = serializers.CharField()
    status = serializers.CharField()
    verified_booking = serializers.BooleanField()
    created_at = serializers.DateTimeField()


class StaffActionOutputSerializer(serializers.Serializer):
    status = serializers.CharField()


def _report_data(report):
    booking = report.booking
    return {
        "id": str(report.pk),
        "reporter": report.reporter.along_account.display_name,
        "reported": report.reported.along_account.display_name,
        "booking_id": str(report.booking_id) if report.booking_id else None,
        "review_id": str(report.review_id) if report.review_id else None,
        "experience_title": booking.snapshot.get("title", booking.experience.title) if booking else "",
        "reason": report.reason,
        "description": report.description,
        "status": report.status,
        "created_at": report.created_at,
        "incident_status": report.incident.status if hasattr(report, "incident") else "",
    }


class StaffDashboardView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        expire_event_collections()
        bookings = Booking.objects.select_related("customer__along_account", "host__user__along_account", "experience").order_by("-created_at")[:50]
        payments = PaymentTransaction.objects.select_related("booking").order_by("-created_at")[:50]
        reports = SafetyReport.objects.select_related(
            "reporter__along_account",
            "reported__along_account",
            "booking__experience",
            "incident",
        ).order_by("-created_at")[:50]
        reviews = Review.objects.filter(status=Review.Status.PENDING).select_related(
            "booking", "reviewer__along_account", "host__user__along_account"
        ).order_by("created_at")[:50]
        pending_applications = HostProfile.objects.filter(
            status__in=[HostProfile.Status.SUBMITTED, HostProfile.Status.UNDER_REVIEW]
        ).count()
        return Response(
            {
                "counts": {
                    "bookings": Booking.objects.count(),
                    "payments": PaymentTransaction.objects.count(),
                    "open_reports": SafetyReport.objects.filter(
                        status__in=[SafetyReport.Status.OPEN, SafetyReport.Status.REVIEWING]
                    ).count(),
                    "pending_reviews": Review.objects.filter(status=Review.Status.PENDING).count(),
                    "pending_applications": pending_applications,
                    "active_collections": EventCollection.objects.filter(
                        status=EventCollection.Status.ACTIVE
                    ).count(),
                },
                "can_suspend_accounts": request.user.is_superuser,
                "bookings": [
                    {
                        "id": str(booking.pk),
                        "experience_title": booking.snapshot.get("title", booking.experience.title),
                        "customer": booking.customer.along_account.display_name,
                        "host": booking.host.user.along_account.display_name,
                        "status": booking.status,
                        "start_at": booking.start_at,
                        "total_minor": booking.total_minor,
                        "currency": booking.currency,
                    }
                    for booking in bookings
                ],
                "payments": [
                    {
                        "id": str(payment.pk),
                        "booking_id": str(payment.booking_id),
                        "provider": payment.provider,
                        "status": payment.status,
                        "amount_minor": payment.amount_minor,
                        "currency": payment.currency,
                        "created_at": payment.created_at,
                    }
                    for payment in payments
                ],
                "reports": [_report_data(report) for report in reports],
                "reviews": [
                    {
                        "id": str(review.pk),
                        "booking_id": str(review.booking_id),
                        "experience_title": review.booking.snapshot.get("title", review.booking.experience.title),
                        "reviewer": review.reviewer.along_account.display_name,
                        "host": review.host.user.along_account.display_name,
                        "rating": review.rating,
                        "comment": review.comment,
                        "private_safety_feedback": review.private_safety_feedback,
                        "status": review.status,
                        "verified_booking": review.booking.status == Booking.Status.COMPLETED,
                        "created_at": review.created_at,
                    }
                    for review in reviews
                ],
                "audit_log_count": AuditLog.objects.count(),
            }
        )


class StaffReportListView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses=StaffReportOutputSerializer(many=True))
    def get(self, request):
        reports = SafetyReport.objects.select_related(
            "reporter__along_account",
            "reported__along_account",
            "booking__experience",
            "incident",
        ).order_by("status", "-created_at")[:200]
        return Response([_report_data(report) for report in reports])


class StaffReportActionView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @transaction.atomic
    @extend_schema(
        request=StaffReportActionSerializer,
        responses=StaffActionOutputSerializer,
    )
    def post(self, request, report_id):
        serializer = StaffReportActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = get_object_or_404(
            SafetyReport.objects.select_for_update(),
            pk=report_id,
        )
        action = serializer.validated_data["action"]
        report.assigned_admin = request.user
        report.status = {
            "review": SafetyReport.Status.REVIEWING,
            "resolve": SafetyReport.Status.RESOLVED,
            "dismiss": SafetyReport.Status.DISMISSED,
            "suspend": SafetyReport.Status.RESOLVED,
        }[action]
        report.save(update_fields=["assigned_admin", "status", "updated_at"])
        if hasattr(report, "incident"):
            incident = report.incident
            incident.status = report.status
            incident.resolution_notes = serializer.validated_data.get("resolution_notes", "")
            incident.save(update_fields=["status", "resolution_notes", "updated_at"])
            record_admin_action(
                request.user,
                f"safety_report_{action}",
                incident,
                {"report_id": str(report.pk)},
            )
        record_admin_action(
            request.user,
            f"safety_report_{action}",
            report,
            {"reason": report.reason, "booking_id": str(report.booking_id) if report.booking_id else None},
        )
        if action == "suspend":
            if not request.user.is_superuser:
                raise PermissionDenied("Only superusers can suspend accounts.")
            account = report.reported.along_account
            account.status = User.Status.SUSPENDED
            account.save(update_fields=["status", "updated_at"])
            auth_user = report.reported
            auth_user.is_active = False
            auth_user.save(update_fields=["is_active"])
            HostProfile.objects.filter(user=auth_user).update(status=HostProfile.Status.SUSPENDED)
            Experience.objects.filter(host__user=auth_user).exclude(
                status=Experience.Status.INACTIVE
            ).update(status=Experience.Status.INACTIVE)
            record_admin_action(
                request.user,
                "account_suspended",
                account,
                {"report_id": str(report.pk)},
            )
        return Response({"status": report.status})


class StaffReviewListView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses=StaffReviewOutputSerializer(many=True))
    def get(self, request):
        reviews = Review.objects.select_related(
            "booking", "reviewer__along_account", "host__user__along_account"
        ).order_by("status", "-created_at")[:200]
        return Response(
            [
                {
                    "id": str(review.pk),
                    "booking_id": str(review.booking_id),
                    "experience_title": review.booking.snapshot.get("title", review.booking.experience.title),
                    "reviewer": review.reviewer.along_account.display_name,
                    "host": review.host.user.along_account.display_name,
                    "rating": review.rating,
                    "comment": review.comment,
                    "private_safety_feedback": review.private_safety_feedback,
                    "status": review.status,
                    "verified_booking": review.booking.status == Booking.Status.COMPLETED,
                    "created_at": review.created_at,
                }
                for review in reviews
            ]
        )


class StaffReviewActionView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @transaction.atomic
    @extend_schema(
        request=StaffReviewActionSerializer,
        responses=StaffActionOutputSerializer,
    )
    def post(self, request, review_id):
        serializer = StaffReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = get_object_or_404(Review.objects.select_for_update(), pk=review_id)
        if review.status != Review.Status.PENDING:
            return Response({"detail": "This review has already been moderated."}, status=status.HTTP_409_CONFLICT)
        action = serializer.validated_data["action"]
        review.status = Review.Status.PUBLISHED if action == "approve" else Review.Status.HIDDEN
        review.save(update_fields=["status", "updated_at"])
        published = Review.objects.filter(
            host=review.host,
            status=Review.Status.PUBLISHED,
            booking__status=Booking.Status.COMPLETED,
        )
        if published.exists():
            review.host.average_rating = published.aggregate(value=Avg("rating"))["value"]
        else:
            review.host.average_rating = 0
        review.host.save(update_fields=["average_rating", "updated_at"])
        record_admin_action(
            request.user,
            f"review_{action}d" if action == "approve" else "review_rejected",
            review,
            {"rating": review.rating},
        )
        if action == "approve":
            enqueue_email(
                review.host.user,
                "review_received",
                "review",
                review.pk,
                {"rating": review.rating},
            )
        return Response({"status": review.status})


class StaffAccountSuspensionView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @transaction.atomic
    @extend_schema(
        request=AccountSuspensionSerializer,
        responses=StaffActionOutputSerializer,
    )
    def post(self, request, account_id):
        if not request.user.is_superuser:
            raise PermissionDenied("Only superusers can change account suspension.")
        account = get_object_or_404(User.objects.select_for_update().select_related("auth_user"), pk=account_id)
        serializer = AccountSuspensionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account.status = serializer.validated_data["status"]
        account.save(update_fields=["status", "updated_at"])
        auth_user = account.auth_user
        auth_user.is_active = account.status == User.Status.ACTIVE
        auth_user.save(update_fields=["is_active"])
        host = HostProfile.objects.filter(user=auth_user).first()
        if host:
            host.status = HostProfile.Status.SUSPENDED if account.status == User.Status.SUSPENDED else HostProfile.Status.UNDER_REVIEW
            host.save(update_fields=["status", "updated_at"])
        record_admin_action(
            request.user,
            f"account_{account.status}",
            account,
            {},
        )
        return Response({"status": account.status})
