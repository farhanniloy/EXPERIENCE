from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def home(request):
    return redirect("openapi-docs")


def healthcheck(request):
    return JsonResponse(
        {
            "status": "ok",
            "service": "along-backend",
            "environment": "development" if settings.DEBUG else "production",
            "timezone": settings.TIME_ZONE,
        }
    )


urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("api/v1/health/", healthcheck, name="health-check"),
    path("api/schema/", SpectacularAPIView.as_view(), name="openapi-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="openapi-schema"),
        name="openapi-docs",
    ),
    path("api/v1/", include("modules.platform.urls")),
    path("api/v1/", include("modules.discovery.urls")),
]
