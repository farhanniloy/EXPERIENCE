from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .models import (
    Category,
    EventCollection,
    Experience,
    HostProfile,
    User,
)


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    display_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False, min_length=8)

    def validate_email(self, value):
        value = value.strip().lower()
        if (
            User.objects.filter(email__iexact=value).exists()
            or get_user_model().objects.filter(email__iexact=value).exists()
        ):
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class CsrfTokenSerializer(serializers.Serializer):
    csrfToken = serializers.CharField()


class UserMeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "display_name", "country_code", "timezone", "locale", "is_email_verified"]
        read_only_fields = ["id", "email", "country_code", "is_email_verified"]


class PublicHostSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.along_account.display_name")
    rating = serializers.DecimalField(source="average_rating", max_digits=3, decimal_places=2)

    class Meta:
        model = HostProfile
        fields = [
            "id", "slug", "name", "city", "headline", "biography", "languages",
            "interests", "verified", "rating", "completed_bookings", "image",
        ]

class PublicCategorySerializer(serializers.ModelSerializer):
    count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ["id", "slug", "name", "description", "icon", "cover_image", "count"]


class PublicExperienceSerializer(serializers.ModelSerializer):
    host = PublicHostSerializer(read_only=True)
    category = serializers.SerializerMethodField()
    city = serializers.CharField(source="host.city", read_only=True)
    host_name = serializers.CharField(source="host.user.along_account.display_name", read_only=True)
    instant_book = serializers.BooleanField(source="instant_booking_enabled", read_only=True)
    image = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

    class Meta:
        model = Experience
        fields = [
            "id", "slug", "title", "summary", "description", "city", "host", "host_name",
            "price_minor", "currency", "duration_minutes", "category", "rating",
            "instant_booking_enabled", "instant_book", "image", "tags",
        ]

    def get_category(self, obj) -> str:
        category = obj.categories.order_by("sort_order", "name").first()
        return category.slug if category else ""

    def get_image(self, obj) -> str:
        media = obj.media.order_by("sort_order").first()
        return media.object_key if media else "/placeholder-experience.svg"

    def get_tags(self, obj) -> list[str]:
        return list(obj.categories.order_by("sort_order", "name").values_list("name", flat=True))


class PublicCollectionSerializer(serializers.ModelSerializer):
    experiences = serializers.SerializerMethodField()
    image = serializers.CharField(source="banner_image", read_only=True)

    class Meta:
        model = EventCollection
        fields = ["id", "slug", "title", "description", "city", "image", "experiences"]

    @extend_schema_field(PublicExperienceSerializer(many=True))
    def get_experiences(self, obj):
        selected = Experience.objects.filter(
            collections=obj,
            status=Experience.Status.PUBLISHED,
            host__status=HostProfile.Status.APPROVED,
            host__user__along_account__status=User.Status.ACTIVE,
        ).select_related("host", "host__user", "host__user__along_account").prefetch_related(
            "categories", "media"
        )
        return PublicExperienceSerializer(selected, many=True, context=self.context).data
