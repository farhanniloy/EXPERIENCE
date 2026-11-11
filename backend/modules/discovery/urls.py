from django.urls import path

from .views import public_marketplace

urlpatterns = [
    path("public/marketplace/", public_marketplace, name="public-marketplace"),
]
