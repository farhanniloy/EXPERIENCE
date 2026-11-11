from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsBookingParty(BasePermission):
    def has_object_permission(self, request, view, obj):
        auth_user = request.user
        if not auth_user.is_authenticated:
            return False
        account_id = auth_user.pk

        booking = getattr(obj, "booking", obj)
        if hasattr(obj, "conversation"):
            booking = obj.conversation.booking
        host_id = getattr(getattr(booking, "host", None), "user_id", None)
        customer_id = getattr(booking, "customer_id", None)
        return account_id in {host_id, customer_id}


class PublicReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS
