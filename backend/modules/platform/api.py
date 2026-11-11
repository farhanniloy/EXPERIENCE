from django.utils import timezone
from rest_framework.pagination import CursorPagination as BaseCursorPagination


class CursorPagination(BaseCursorPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-created_at"

    def get_ordering(self, request, queryset, view):
        orderings = {
            "price": ("price_minor", "id"),
            "-price": ("-price_minor", "id"),
            "rating": ("-rating", "id"),
            "recent": ("-created_at", "id"),
            "relevance": ("-created_at", "id"),
        }
        selected = request.query_params.get("sort", "relevance")
        if selected not in orderings:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"sort": "Use relevance, price, -price, rating, or recent."})
        return orderings[selected]

    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        response.data["generated_at"] = timezone.now()
        return response
