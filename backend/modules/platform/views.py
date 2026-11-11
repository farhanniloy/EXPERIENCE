from datetime import date
from urllib.parse import urlencode

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.utils.decorators import method_decorator
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from .api import CursorPagination
from config.product import BRAND_NAME

from .models import (
    Category,
    EventCollection,
    Experience,
    HostProfile,
    User,
)
from .serializers import (
    CsrfTokenSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PublicCategorySerializer,
    PublicCollectionSerializer,
    PublicExperienceSerializer,
    PublicHostSerializer,
    RegisterSerializer,
    UserMeSerializer,
)
from .services import expire_event_collections


def get_or_create_account(auth_user):
    account, _ = User.objects.get_or_create(
        auth_user=auth_user,
        defaults={
            "email": auth_user.email.strip().lower(),
            "display_name": auth_user.get_full_name(),
        },
    )
    return account


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "register"

    @method_decorator(csrf_protect)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    @extend_schema(request=RegisterSerializer, responses={201: UserMeSerializer})
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserMeSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "login"

    @method_decorator(csrf_protect)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    @extend_schema(request=LoginSerializer, responses={200: UserMeSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        user = authenticate(request, email=email, password=serializer.validated_data["password"])
        if user is None or not user.is_active:
            return Response(
                {"error": {"code": "INVALID_CREDENTIALS", "message": "Email or password is incorrect."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        account = get_or_create_account(user)
        if account.status != User.Status.ACTIVE:
            return Response(
                {"error": {"code": "INVALID_CREDENTIALS", "message": "Email or password is incorrect."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        return Response(UserMeSerializer(account).data)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "password_reset"

    @extend_schema(request=PasswordResetRequestSerializer, responses={202: None})
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        user = get_user_model().objects.filter(email__iexact=email, is_active=True).first()
        if user:
            token = default_token_generator.make_token(user)
            query = urlencode({"email": user.email, "token": token})
            reset_url = request.build_absolute_uri(f"/api/v1/auth/password/confirm?{query}")
            send_mail(
                f"Reset your {BRAND_NAME} password",
                f"Use this password reset link to continue: {reset_url}",
                None,
                [user.email],
                fail_silently=False,
            )
        return Response(
            {"detail": "If an account exists for that email, password reset instructions will be sent."},
            status=status.HTTP_202_ACCEPTED,
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=PasswordResetConfirmSerializer, responses={200: None})
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.initial_data.get("email") or not serializer.initial_data.get("token"):
            data = request.data.copy()
            data.setdefault("email", request.query_params.get("email", ""))
            data.setdefault("token", request.query_params.get("token", ""))
            serializer = PasswordResetConfirmSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        user = get_user_model().objects.filter(email__iexact=values["email"].strip().lower(), is_active=True).first()
        if user is None or not default_token_generator.check_token(user, values["token"]):
            return Response(
                {"error": {"code": "INVALID_RESET_TOKEN", "message": "The password reset link is invalid or expired."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(values["new_password"])
        user.save(update_fields=["password"])
        return Response({"detail": "Password updated."})


class UserMeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserMeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        account = get_or_create_account(self.request.user)
        if account.status != User.Status.ACTIVE:
            raise PermissionDenied("This account is not active.")
        return account


class CsrfTokenView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(responses=CsrfTokenSerializer)
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class CategoryListView(generics.ListAPIView):
    serializer_class = PublicCategorySerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        return Category.objects.filter(is_active=True).annotate(
            count=Count(
                "experiences",
                filter=Q(
                    experiences__status=Experience.Status.PUBLISHED,
                    experiences__host__status=HostProfile.Status.APPROVED,
                    experiences__host__user__along_account__status=User.Status.ACTIVE,
                ),
                distinct=True,
            )
        )


class CatalogCursorPagination(CursorPagination):
    ordering = "-created_at"


class HostCursorPagination(CursorPagination):
    ordering = "-created_at"

    def get_ordering(self, request, queryset, view):
        orderings = {
            "relevance": ("-created_at", "id"),
            "recent": ("-created_at", "id"),
            "rating": ("-average_rating", "id"),
        }
        selected = request.query_params.get("sort", "relevance")
        if selected not in orderings:
            raise ValidationError({"sort": "Use relevance, rating, or recent."})
        return orderings[selected]


class ExperienceListView(generics.ListAPIView):
    serializer_class = PublicExperienceSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = CatalogCursorPagination

    @extend_schema(
        parameters=[
            OpenApiParameter("category", OpenApiTypes.STR),
            OpenApiParameter("q", OpenApiTypes.STR),
            OpenApiParameter("city", OpenApiTypes.STR),
            OpenApiParameter("budget", OpenApiTypes.INT, description="Maximum price in currency minor units."),
            OpenApiParameter("date", OpenApiTypes.DATE),
            OpenApiParameter("duration", OpenApiTypes.INT),
            OpenApiParameter("min_duration", OpenApiTypes.INT),
            OpenApiParameter("max_duration", OpenApiTypes.INT),
            OpenApiParameter("min_rating", OpenApiTypes.NUMBER),
            OpenApiParameter("language", OpenApiTypes.STR),
            OpenApiParameter("instant_booking", OpenApiTypes.BOOL),
            OpenApiParameter("verified", OpenApiTypes.BOOL),
            OpenApiParameter("sort", OpenApiTypes.STR, enum=["relevance", "price", "-price", "rating", "recent"]),
            OpenApiParameter("cursor", OpenApiTypes.STR),
            OpenApiParameter("page_size", OpenApiTypes.INT),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Experience.objects.filter(
            status=Experience.Status.PUBLISHED,
            host__status=HostProfile.Status.APPROVED,
            host__user__along_account__status=User.Status.ACTIVE,
        ).select_related("host", "host__user", "host__user__along_account").prefetch_related(
            "categories", "media"
        )
        params = self.request.query_params

        category = params.get("category")
        if category:
            queryset = queryset.filter(categories__slug=category)
        city = params.get("city")
        if city:
            queryset = queryset.filter(host__city__iexact=city.strip())
        query = params.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(summary__icontains=query)
                | Q(description__icontains=query)
                | Q(host__user__along_account__display_name__icontains=query)
            )
        budget = params.get("budget")
        if budget:
            try:
                budget_minor = int(budget)
                if budget_minor < 0:
                    raise ValueError
            except ValueError as exc:
                raise ValidationError({"budget": "Budget must be a non-negative integer in minor units."}) from exc
            queryset = queryset.filter(price_minor__lte=budget_minor)

        duration = params.get("duration")
        if duration:
            queryset = queryset.filter(duration_minutes=positive_integer(duration, "duration"))
        min_duration = params.get("min_duration")
        if min_duration:
            queryset = queryset.filter(duration_minutes__gte=positive_integer(min_duration, "min_duration"))
        max_duration = params.get("max_duration")
        if max_duration:
            queryset = queryset.filter(duration_minutes__lte=positive_integer(max_duration, "max_duration"))
        min_rating = params.get("min_rating")
        if min_rating:
            try:
                rating = float(min_rating)
                if not 0 <= rating <= 5:
                    raise ValueError
            except ValueError as exc:
                raise ValidationError({"min_rating": "Rating must be between 0 and 5."}) from exc
            queryset = queryset.filter(rating__gte=rating)
        language = params.get("language")
        if language:
            queryset = queryset.filter(host__languages__icontains=language.strip())
        instant = params.get("instant_booking")
        if instant is not None:
            queryset = queryset.filter(instant_booking_enabled=parse_boolean(instant, "instant_booking"))
        verified = params.get("verified")
        if verified is not None:
            queryset = queryset.filter(host__verified=parse_boolean(verified, "verified"))

        date_filter = params.get("date")
        if date_filter:
            try:
                selected_date = date.fromisoformat(date_filter)
            except ValueError as exc:
                raise ValidationError({"date": "Date must use YYYY-MM-DD format."}) from exc
            host_ids = HostProfile.objects.filter(
                Q(availability_rules__weekday=selected_date.weekday(), availability_rules__is_active=True)
                | Q(
                    availability_exceptions__exception_type="available",
                    availability_exceptions__start_at__date__lte=selected_date,
                    availability_exceptions__end_at__date__gte=selected_date,
                )
            ).exclude(
                availability_exceptions__exception_type="unavailable",
                availability_exceptions__start_at__date__lte=selected_date,
                availability_exceptions__end_at__date__gte=selected_date,
            ).values("id")
            queryset = queryset.filter(host_id__in=host_ids)

        sort = params.get("sort", "relevance")
        if sort not in {"relevance", "price", "-price", "rating", "recent"}:
            raise ValidationError({"sort": "Use relevance, price, -price, rating, or recent."})
        return queryset.distinct()


class ExperienceDetailView(generics.RetrieveAPIView):
    serializer_class = PublicExperienceSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"
    queryset = Experience.objects.filter(
        status=Experience.Status.PUBLISHED,
        host__status=HostProfile.Status.APPROVED,
        host__user__along_account__status=User.Status.ACTIVE,
    ).select_related("host", "host__user", "host__user__along_account").prefetch_related(
        "categories", "media"
    )


class HostListView(generics.ListAPIView):
    serializer_class = PublicHostSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = HostCursorPagination

    def get_queryset(self):
        queryset = HostProfile.objects.filter(
            status=HostProfile.Status.APPROVED, user__along_account__status=User.Status.ACTIVE
        ).select_related("user", "user__along_account")
        city = self.request.query_params.get("city")
        query = self.request.query_params.get("q", "").strip()
        if city:
            queryset = queryset.filter(city__iexact=city.strip())
        if query:
            queryset = queryset.filter(
                Q(user__along_account__display_name__icontains=query)
                | Q(headline__icontains=query)
                | Q(biography__icontains=query)
            )
        verified = self.request.query_params.get("verified")
        if verified is not None:
            queryset = queryset.filter(verified=parse_boolean(verified, "verified"))
        return queryset


class HostDetailView(generics.RetrieveAPIView):
    serializer_class = PublicHostSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"
    queryset = HostProfile.objects.filter(
        status=HostProfile.Status.APPROVED, user__along_account__status=User.Status.ACTIVE
    ).select_related("user", "user__along_account")


class CollectionListView(generics.ListAPIView):
    serializer_class = PublicCollectionSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = CatalogCursorPagination

    def get_queryset(self):
        expire_event_collections()
        now = timezone.now()
        return EventCollection.objects.filter(status=EventCollection.Status.ACTIVE).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now),
            Q(ends_at__isnull=True) | Q(ends_at__gt=now),
        ).prefetch_related("experiences")


class CollectionDetailView(generics.RetrieveAPIView):
    serializer_class = PublicCollectionSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        expire_event_collections()
        now = timezone.now()
        return EventCollection.objects.filter(status=EventCollection.Status.ACTIVE).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now),
            Q(ends_at__isnull=True) | Q(ends_at__gt=now),
        ).prefetch_related("experiences")


def positive_integer(value, field):
    try:
        result = int(value)
        if result <= 0:
            raise ValueError
        return result
    except ValueError as exc:
        raise ValidationError({field: "Value must be a positive integer."}) from exc


def parse_boolean(value, field):
    normalized = value.lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValidationError({field: "Value must be true or false."})
