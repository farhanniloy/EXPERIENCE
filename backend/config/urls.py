from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


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
    path("admin/", admin.site.urls),
    path("api/v1/health/", healthcheck, name="health-check"),
    path("api/v1/", include("modules.discovery.urls")),
]
