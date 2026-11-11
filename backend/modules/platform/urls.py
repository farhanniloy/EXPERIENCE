from django.urls import path

from .views import (
    CategoryListView,
    CsrfTokenView,
    CollectionDetailView,
    CollectionListView,
    ExperienceDetailView,
    ExperienceListView,
    HostDetailView,
    HostListView,
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    UserMeView,
)

urlpatterns = [
    path("auth/csrf", CsrfTokenView.as_view(), name="auth-csrf"),
    path("auth/register", RegisterView.as_view(), name="auth-register"),
    path("auth/login", LoginView.as_view(), name="auth-login"),
    path("auth/logout", LogoutView.as_view(), name="auth-logout"),
    path("auth/password/reset", PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("auth/password/confirm", PasswordResetConfirmView.as_view(), name="auth-password-confirm"),
    path("users/me", UserMeView.as_view(), name="users-me"),
    path("categories", CategoryListView.as_view(), name="category-list"),
    path("experiences", ExperienceListView.as_view(), name="experience-list"),
    path("experiences/<slug:slug>", ExperienceDetailView.as_view(), name="experience-detail"),
    path("companions", HostListView.as_view(), name="host-list"),
    path("companions/<slug:slug>", HostDetailView.as_view(), name="host-detail"),
    path("collections", CollectionListView.as_view(), name="collection-list"),
    path("collections/<slug:slug>", CollectionDetailView.as_view(), name="collection-detail"),
]
