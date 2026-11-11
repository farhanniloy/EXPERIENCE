import uuid
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from config.product import COUNTRY_CODE, CURRENCY_CODE, LAUNCH_CITY

from .models import (
    Booking,
    Category,
    Experience,
    ExperienceMedia,
    HostProfile,
    ModerationQueueItem,
    User,
    VerificationCheck,
)
from .moderation import (
    flag_host_profile,
    queue_host_application,
    queue_profile_content,
)
from .services import (
    apply_moderation_decision,
    deactivate_experience,
    submit_experience_for_publication,
)


class HostApplicationDataSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    headline = serializers.CharField(max_length=180, required=False, allow_blank=True)
    biography = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    languages = serializers.ListField(
        child=serializers.CharField(max_length=40), required=False, allow_empty=True
    )
    interests = serializers.ListField(
        child=serializers.CharField(max_length=60), required=False, allow_empty=True
    )
    photos = serializers.ListField(
        child=serializers.CharField(max_length=500), required=False, allow_empty=True, max_length=6
    )

    def validate_photos(self, values):
        for value in values:
            parsed = urlparse(value)
            if value.startswith("/"):
                if value.startswith("//") or ".." in value:
                    raise serializers.ValidationError("Use a local path or HTTPS photo URL.")
            elif parsed.scheme != "https" or not parsed.netloc:
                raise serializers.ValidationError("Photos must use a local path or HTTPS URL.")
        return values


class ExperienceWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=180)
    description = serializers.CharField()
    summary = serializers.CharField(max_length=300, required=False, allow_blank=True)
    duration_minutes = serializers.IntegerField(min_value=15, max_value=1440)
    min_duration_minutes = serializers.IntegerField(min_value=15, max_value=1440, required=False, allow_null=True)
    max_duration_minutes = serializers.IntegerField(min_value=15, max_value=1440, required=False, allow_null=True)
    pricing_type = serializers.ChoiceField(choices=Experience.PricingType.choices, required=False)
    price_minor = serializers.IntegerField(min_value=0)
    instant_booking_enabled = serializers.BooleanField(required=False)
    category_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True, max_length=10
    )
    image = serializers.CharField(max_length=500, required=False, allow_blank=True)
    submit_for_review = serializers.BooleanField(required=False, default=False)

    def validate_image(self, value):
        if not value:
            return value
        parsed = urlparse(value)
        if value.startswith("/"):
            if value.startswith("//") or ".." in value:
                raise serializers.ValidationError("Use a local path or HTTPS image URL.")
        elif parsed.scheme != "https" or not parsed.netloc:
            raise serializers.ValidationError("Images must use a local path or HTTPS URL.")
        return value

    def validate_category_ids(self, values):
        if Category.objects.filter(id__in=values, is_active=True).count() != len(set(values)):
            raise serializers.ValidationError("Choose only active marketplace categories.")
        return values

    def validate(self, attrs):
        minimum = attrs.get("min_duration_minutes")
        maximum = attrs.get("max_duration_minutes")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise serializers.ValidationError(
                {"max_duration_minutes": "Maximum duration must be at least the minimum duration."}
            )
        return attrs


class HostProfileOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    display_name = serializers.CharField()
    headline = serializers.CharField()
    biography = serializers.CharField()
    city = serializers.CharField()
    languages = serializers.ListField(child=serializers.CharField())
    interests = serializers.ListField(child=serializers.CharField())
    photos = serializers.ListField(child=serializers.CharField())
    status = serializers.CharField()
    adult_confirmed = serializers.BooleanField()
    verification_provider = serializers.CharField(allow_null=True)
    verified = serializers.BooleanField()


class VerificationOutputSerializer(serializers.Serializer):
    status = serializers.CharField()
    provider = serializers.CharField()
    label = serializers.CharField()


class AgeConfirmationSerializer(serializers.Serializer):
    confirmed_18 = serializers.BooleanField()


class ManagedExperienceOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    slug = serializers.SlugField()
    title = serializers.CharField()
    summary = serializers.CharField()
    description = serializers.CharField()
    duration_minutes = serializers.IntegerField()
    min_duration_minutes = serializers.IntegerField(allow_null=True)
    max_duration_minutes = serializers.IntegerField(allow_null=True)
    pricing_type = serializers.CharField()
    price_minor = serializers.IntegerField()
    currency = serializers.CharField()
    instant_booking_enabled = serializers.BooleanField()
    status = serializers.CharField()
    category_ids = serializers.ListField(child=serializers.UUIDField())
    image = serializers.CharField()


class BookingSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()
    experience_title = serializers.CharField()
    other_party = serializers.CharField()
    total_minor = serializers.IntegerField()
    currency = serializers.CharField()


class CustomerDashboardOutputSerializer(serializers.Serializer):
    display_name = serializers.CharField()
    bookings = BookingSummarySerializer(many=True)


class HostDashboardOutputSerializer(serializers.Serializer):
    host = HostProfileOutputSerializer()
    experiences = ManagedExperienceOutputSerializer(many=True)
    bookings = BookingSummarySerializer(many=True)


class ModerationExperienceOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    status = serializers.CharField()


class ModerationItemOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    queue_type = serializers.CharField()
    flagged_fields = serializers.DictField(child=serializers.ListField(child=serializers.CharField()))
    content = serializers.DictField(child=serializers.CharField())
    host = serializers.CharField()
    host_slug = serializers.CharField()
    host_status = serializers.CharField()
    experience = ModerationExperienceOutputSerializer(allow_null=True)
    created_at = serializers.DateTimeField()


class ModerationActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])


class ModerationActionOutputSerializer(serializers.Serializer):
    status = serializers.CharField()


class WriteThrottledAPIView(APIView):
    def get_throttles(self):
        if self.request.method in permissions.SAFE_METHODS:
            return []
        return super().get_throttles()


def get_host_profile(auth_user):
    account, _ = User.objects.get_or_create(
        auth_user=auth_user,
        defaults={"email": auth_user.email.strip().lower()},
    )
    name = account.display_name or auth_user.get_username()
    base_slug = slugify(name)[:120] or "host"
    host, _ = HostProfile.objects.get_or_create(
        user=auth_user,
        defaults={
            "slug": f"{base_slug}-{uuid.uuid4().hex[:8]}",
            "city": LAUNCH_CITY,
            "country_code": COUNTRY_CODE,
        },
    )
    return account, host


def serialize_host(account, host):
    age_check = VerificationCheck.objects.filter(
        user=host.user,
        check_type=VerificationCheck.CheckType.AGE,
        status=VerificationCheck.Status.APPROVED,
    ).filter(models_expiry_filter()).order_by("-created_at").first()
    return {
        "id": str(host.id),
        "display_name": account.display_name,
        "headline": host.headline,
        "biography": host.biography,
        "city": host.city,
        "languages": host.languages,
        "interests": host.interests,
        "photos": host.photos,
        "status": host.status,
        "adult_confirmed": age_check is not None,
        "verification_provider": age_check.provider if age_check else None,
        "verified": host.verified,
    }


class CompanionMeView(WriteThrottledAPIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "host_onboarding"

    @extend_schema(responses=HostProfileOutputSerializer)
    def get(self, request):
        account, host = get_host_profile(request.user)
        return Response(serialize_host(account, host))

    @extend_schema(request=HostApplicationDataSerializer, responses=HostProfileOutputSerializer)
    def patch(self, request):
        account, host = get_host_profile(request.user)
        serializer = HostApplicationDataSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        display_name = values.pop("display_name", None)
        if display_name is not None:
            account.display_name = display_name.strip()
            account.save(update_fields=["display_name", "updated_at"])
        for field in ("headline", "biography", "city", "languages", "interests", "photos"):
            if field in values:
                setattr(host, field, values[field])
        if "photos" in values:
            host.image = values["photos"][0] if values["photos"] else "/placeholder-host.svg"
        host.country_code = COUNTRY_CODE
        host.save()

        flagged = flag_host_profile(host)
        if flagged:
            if host.status == HostProfile.Status.APPROVED:
                queue_profile_content(host, flagged)
                host.status = HostProfile.Status.UNDER_REVIEW
                host.save(update_fields=["status", "updated_at"])
            elif host.status == HostProfile.Status.SUBMITTED:
                queue_host_application(host, flagged)
        elif host.status == HostProfile.Status.SUBMITTED:
            queue_host_application(host, {})
        elif host.status == HostProfile.Status.UNDER_REVIEW:
            queue_profile_content(host, {})
        return Response(serialize_host(account, host))


class CompanionApplicationView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "host_onboarding"

    @transaction.atomic
    @extend_schema(request=HostApplicationDataSerializer, responses=HostProfileOutputSerializer)
    def post(self, request):
        account, host = get_host_profile(request.user)
        if host.status == HostProfile.Status.APPROVED:
            raise ValidationError("This host profile is already approved.")
        serializer = HostApplicationDataSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        display_name = values.pop("display_name", None)
        if display_name:
            account.display_name = display_name.strip()
            account.save(update_fields=["display_name", "updated_at"])
        for field in ("headline", "biography", "city", "languages", "interests", "photos"):
            if field in values:
                setattr(host, field, values[field])
        if "photos" in values:
            host.image = values["photos"][0] if values["photos"] else "/placeholder-host.svg"
        if not host.city.strip() or not account.display_name.strip() or not host.headline.strip():
            raise ValidationError("Display name, headline, and service city are required.")
        if not host.languages or not host.interests:
            raise ValidationError("Add at least one language and one interest before submitting.")
        if not VerificationCheck.objects.filter(
            user=request.user,
            check_type=VerificationCheck.CheckType.AGE,
            status=VerificationCheck.Status.APPROVED,
        ).filter(models_expiry_filter()).exists():
            raise ValidationError("Complete the adults-only confirmation step before submitting.")

        host.status = HostProfile.Status.SUBMITTED
        host.country_code = COUNTRY_CODE
        host.save()
        queue_host_application(host, flag_host_profile(host))
        return Response(serialize_host(account, host), status=status.HTTP_202_ACCEPTED)


def models_expiry_filter():
    from django.db.models import Q

    return Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())


class DevelopmentAgeVerificationView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "host_onboarding"

    @extend_schema(
        request=AgeConfirmationSerializer,
        responses=VerificationOutputSerializer,
    )
    def post(self, request):
        if not settings.DEBUG or settings.APP_ENV in {"prod", "production"}:
            raise PermissionDenied("The development verification adapter is disabled.")
        if request.data.get("confirmed_18") is not True:
            raise ValidationError({"confirmed_18": "Confirm that you are at least 18 years old."})
        VerificationCheck.objects.update_or_create(
            user=request.user,
            check_type=VerificationCheck.CheckType.AGE,
            provider="development_mock",
            defaults={
                "status": VerificationCheck.Status.APPROVED,
                "checked_at": timezone.now(),
                "expires_at": timezone.now() + timedelta(days=365),
                "metadata": {"simulation": True, "adult_self_confirmation": True},
            },
        )
        return Response(
            {
                "status": "approved",
                "provider": "development_mock",
                "label": "Development simulation only; this is not identity verification.",
            },
            status=status.HTTP_201_CREATED,
        )

def serialize_managed_experience(experience):
    media = experience.media.order_by("sort_order").first()
    return {
        "id": str(experience.id),
        "slug": experience.slug,
        "title": experience.title,
        "summary": experience.summary,
        "description": experience.description,
        "duration_minutes": experience.duration_minutes,
        "min_duration_minutes": experience.min_duration_minutes,
        "max_duration_minutes": experience.max_duration_minutes,
        "pricing_type": experience.pricing_type,
        "price_minor": experience.price_minor,
        "currency": experience.currency,
        "instant_booking_enabled": experience.instant_booking_enabled,
        "status": experience.status,
        "category_ids": [str(category_id) for category_id in experience.categories.values_list("id", flat=True)],
        "image": media.object_key if media else "/placeholder-experience.svg",
    }


def apply_experience_values(experience, values):
    for field in (
        "title",
        "description",
        "summary",
        "duration_minutes",
        "min_duration_minutes",
        "max_duration_minutes",
        "pricing_type",
        "price_minor",
        "instant_booking_enabled",
    ):
        if field in values:
            setattr(experience, field, values[field])
    image = values.get("image")
    if image:
        ExperienceMedia.objects.update_or_create(
            experience=experience,
            sort_order=0,
            defaults={
                "object_key": image,
                "media_type": ExperienceMedia.MediaType.IMAGE,
                "alt_text": experience.title,
            },
        )
    if "category_ids" in values:
        experience.categories.set(values["category_ids"])


class ManagedExperienceListView(WriteThrottledAPIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "experience_write"

    @extend_schema(responses=ManagedExperienceOutputSerializer(many=True))
    def get(self, request):
        _, host = get_host_profile(request.user)
        return Response(
            [
                serialize_managed_experience(item)
                for item in host.experiences.prefetch_related("categories", "media").order_by("-created_at")
            ]
        )

    @transaction.atomic
    @extend_schema(request=ExperienceWriteSerializer, responses=ManagedExperienceOutputSerializer)
    def post(self, request):
        _, host = get_host_profile(request.user)
        serializer = ExperienceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        submit = values.pop("submit_for_review")
        category_ids = values.pop("category_ids", [])
        image = values.get("image")
        if submit and host.status != HostProfile.Status.APPROVED:
            raise PermissionDenied("Host approval is required before publishing an experience.")
        experience = Experience(
            host=host,
            title=values["title"],
            slug=f"{slugify(values['title'])[:150] or 'experience'}-{uuid.uuid4().hex[:8]}",
            description=values["description"],
            summary=values.get("summary", ""),
            duration_minutes=values["duration_minutes"],
            min_duration_minutes=values.get("min_duration_minutes"),
            max_duration_minutes=values.get("max_duration_minutes"),
            pricing_type=values.get("pricing_type", Experience.PricingType.FIXED),
            price_minor=values["price_minor"],
            currency=CURRENCY_CODE,
            instant_booking_enabled=values.get("instant_booking_enabled", False),
            status=Experience.Status.DRAFT,
        )
        experience.save()
        experience.categories.set(category_ids)
        if image:
            ExperienceMedia.objects.create(
                experience=experience,
                object_key=image,
                media_type=ExperienceMedia.MediaType.IMAGE,
                alt_text=experience.title,
                sort_order=0,
            )
        submit_experience_for_publication(host, experience, submit)
        experience.save(update_fields=["status", "updated_at"])
        return Response(serialize_managed_experience(experience), status=status.HTTP_201_CREATED)


class ManagedExperienceDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "experience_write"

    def get_object(self, request, experience_id):
        _, host = get_host_profile(request.user)
        return get_object_or_404(
            Experience.objects.prefetch_related("categories", "media"),
            pk=experience_id,
            host=host,
        )

    @transaction.atomic
    @extend_schema(request=ExperienceWriteSerializer, responses=ManagedExperienceOutputSerializer)
    def patch(self, request, experience_id):
        experience = self.get_object(request, experience_id)
        _, host = get_host_profile(request.user)
        serializer = ExperienceWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        submit = values.pop("submit_for_review", False)
        apply_experience_values(experience, values)
        submit_experience_for_publication(host, experience, submit)
        experience.save()
        return Response(serialize_managed_experience(experience))

    @extend_schema(responses={204: None})
    def delete(self, request, experience_id):
        experience = self.get_object(request, experience_id)
        deactivate_experience(experience)
        return Response(status=status.HTTP_204_NO_CONTENT)


def serialize_booking(booking, user, host_view=False):
    experience = booking.experience
    if host_view:
        customer = getattr(booking.customer, "along_account", None)
        other_party = customer.display_name if customer else "Customer"
    else:
        other_party = booking.host.user.along_account.display_name
    return {
        "id": str(booking.id),
        "id": str(booking.id),
        "status": booking.status,
        "start_at": booking.start_at.isoformat(),
        "end_at": booking.end_at.isoformat(),
        "experience_title": booking.snapshot.get("title", experience.title),
        "other_party": other_party,
        "total_minor": booking.total_minor,
        "currency": booking.currency,
    }


class CustomerDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=CustomerDashboardOutputSerializer)
    def get(self, request):
        account = User.objects.filter(auth_user=request.user).first()
        bookings = Booking.objects.filter(customer=request.user).select_related(
            "experience", "host__user__along_account"
        ).order_by("-start_at")[:50]
        return Response(
            {
                "display_name": account.display_name if account else "",
                "bookings": [serialize_booking(item, request.user) for item in bookings],
            }
        )


class HostDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=HostDashboardOutputSerializer)
    def get(self, request):
        _, host = get_host_profile(request.user)
        bookings = Booking.objects.filter(host=host).select_related(
            "experience", "customer__along_account"
        ).order_by("-start_at")[:50]
        experiences = host.experiences.order_by("-created_at")
        return Response(
            {
                "host": serialize_host(host.user.along_account, host),
                "experiences": [serialize_managed_experience(item) for item in experiences],
                "bookings": [
                    serialize_booking(item, request.user, host_view=True) for item in bookings
                ],
            }
        )


class ModerationQueueView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses=ModerationItemOutputSerializer(many=True))
    def get(self, request):
        items = ModerationQueueItem.objects.filter(status=ModerationQueueItem.Status.PENDING).select_related(
            "host__user__along_account", "experience"
        ).order_by("created_at")
        return Response(
            [
                {
                    "id": str(item.id),
                    "queue_type": item.queue_type,
                    "flagged_fields": item.flagged_fields,
                    "content": {
                        field: (
                            getattr(item.experience, field, "")
                            if item.experience_id and field != "photos"
                            else "\n".join(item.experience.media.values_list("object_key", flat=True))
                            if item.experience_id
                            else "\n".join(item.host.photos)
                            if field == "photos"
                            else getattr(item.host, field, "")
                        )
                        for field in item.flagged_fields
                    },
                    "host": item.host.user.along_account.display_name,
                    "host_slug": item.host.slug,
                    "host_status": item.host.status,
                    "experience": (
                        {
                            "id": str(item.experience_id),
                            "title": item.experience.title,
                            "status": item.experience.status,
                        }
                        if item.experience_id
                        else None
                    ),
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ]
        )


class ModerationReviewView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @transaction.atomic
    @extend_schema(request=ModerationActionSerializer, responses=ModerationActionOutputSerializer)
    def post(self, request, item_id):
        action = request.data.get("action")
        item = get_object_or_404(
            ModerationQueueItem.objects.select_for_update(),
            pk=item_id,
            status=ModerationQueueItem.Status.PENDING,
        )
        item = apply_moderation_decision(item, action, request.user)
        return Response({"status": item.status})
