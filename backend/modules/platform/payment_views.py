from django.core.exceptions import ImproperlyConfigured, ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PaymentTransaction
from .payments import (
    complete_sandbox_payment,
    create_refund,
    get_payment_adapter,
    initiate_payment,
    process_payment_webhook,
)


class PaymentProviderUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Payment provider is not configured for this environment."
    default_code = "payment_provider_unavailable"


class PaymentInitiateSerializer(serializers.Serializer):
    pass


class PaymentOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    booking_id = serializers.UUIDField()
    booking_status = serializers.CharField()
    status = serializers.CharField()
    provider = serializers.CharField()
    provider_label = serializers.CharField()
    amount_minor = serializers.IntegerField()
    currency = serializers.CharField()
    checkout_url = serializers.CharField(allow_null=True)


class SandboxOutcomeSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=["success", "failure", "expiry"])


class RefundCreateSerializer(serializers.Serializer):
    payment_id = serializers.UUIDField()
    amount_minor = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=250)


class RefundOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    payment_id = serializers.UUIDField()
    amount_minor = serializers.IntegerField()
    currency = serializers.CharField()
    status = serializers.CharField()
    provider_reference = serializers.CharField()


class PaymentWebhookResultSerializer(serializers.Serializer):
    duplicate = serializers.BooleanField()
    result = serializers.CharField()


def _adapter_or_503(provider=None):
    try:
        return get_payment_adapter(provider)
    except ImproperlyConfigured as exc:
        raise PaymentProviderUnavailable() from exc


def serialize_payment(payment, viewer):
    customer_view = payment.booking.customer_id == viewer.pk
    return {
        "id": payment.pk,
        "booking_id": payment.booking_id,
        "booking_status": payment.booking.status,
        "status": payment.status,
        "provider": payment.provider,
        "provider_label": (
            "Sandbox payment simulation — development only"
            if payment.provider == "sandbox"
            else payment.provider
        ),
        "amount_minor": payment.amount_minor,
        "currency": payment.currency,
        "checkout_url": payment.metadata.get("checkout_url") if customer_view else None,
    }


class BookingPaymentCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "payments"

    @extend_schema(
        parameters=[OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=True)],
        request=PaymentInitiateSerializer,
        responses={"201": PaymentOutputSerializer},
    )
    def post(self, request, booking_id):
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key:
            raise ValidationError({"Idempotency-Key": "This header is required."})
        _adapter_or_503()
        serializer = PaymentInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payment = initiate_payment(
                booking_id=booking_id,
                customer=request.user,
                idempotency_key=idempotency_key,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        payment = PaymentTransaction.objects.select_related("booking").get(pk=payment.pk)
        return Response(serialize_payment(payment, request.user), status=status.HTTP_201_CREATED)


class PaymentDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "payments"

    @extend_schema(responses=PaymentOutputSerializer)
    def get(self, request, payment_id):
        payment = get_object_or_404(
            PaymentTransaction.objects.select_related("booking"),
            Q(booking__customer=request.user) | Q(booking__host__user=request.user),
            pk=payment_id,
        )
        return Response(serialize_payment(payment, request.user))


class SandboxPaymentCompleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "payments"

    @extend_schema(request=SandboxOutcomeSerializer, responses=PaymentOutputSerializer)
    def post(self, request, payment_id):
        _adapter_or_503("sandbox")
        serializer = SandboxOutcomeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            complete_sandbox_payment(
                payment_id,
                request.user,
                serializer.validated_data["outcome"],
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        payment = get_object_or_404(
            PaymentTransaction.objects.select_related("booking"),
            pk=payment_id,
            booking__customer=request.user,
        )
        return Response(serialize_payment(payment, request.user))


class PaymentWebhookView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_scope = "payments"

    @extend_schema(
        parameters=[OpenApiParameter("X-Payment-Signature", str, OpenApiParameter.HEADER, required=True)],
        request=None,
        responses={200: PaymentWebhookResultSerializer},
    )
    def post(self, request, provider):
        _adapter_or_503(provider)
        signature = request.headers.get("X-Payment-Signature", "")
        try:
            result = process_payment_webhook(provider, request.body, signature)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response(result)


class RefundCreateView(APIView):
    permission_classes = [permissions.IsAdminUser]
    throttle_scope = "payments"

    @extend_schema(
        parameters=[OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=True)],
        request=RefundCreateSerializer,
        responses={"201": RefundOutputSerializer},
    )
    def post(self, request):
        key = request.headers.get("Idempotency-Key", "").strip()
        if not key:
            raise ValidationError({"Idempotency-Key": "This header is required."})
        serializer = RefundCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            refund = create_refund(
                payment_id=values["payment_id"],
                actor=request.user,
                amount_minor=values["amount_minor"],
                reason=values["reason"],
                idempotency_key=key,
            )
        except ImproperlyConfigured as exc:
            raise PaymentProviderUnavailable() from exc
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response({
            "id": refund.pk,
            "payment_id": refund.payment_id,
            "amount_minor": refund.amount_minor,
            "currency": refund.currency,
            "status": refund.status,
            "provider_reference": refund.provider_reference,
        }, status=status.HTTP_201_CREATED)
