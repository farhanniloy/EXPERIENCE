import json
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse

from config.product import BRAND_NAME, COUNTRY_CODE, CURRENCY_CODE, LAUNCH_CITY, TAGLINE, TIME_ZONE


def _load_marketplace_data():
    fixture_path = Path(settings.BASE_DIR) / "fixtures" / "public_data.json"
    if not fixture_path.exists():
        return {
            "site": {
                "brand": BRAND_NAME,
                "tagline": TAGLINE,
                "currency": CURRENCY_CODE,
                "timezone": TIME_ZONE,
                "country": COUNTRY_CODE,
                "city": LAUNCH_CITY,
            },
            "categories": [],
            "experiences": [],
            "companions": [],
            "collections": [],
        }

    with fixture_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    payload["site"] = {
        **payload.get("site", {}),
        "brand": BRAND_NAME,
        "tagline": TAGLINE,
        "currency": CURRENCY_CODE,
        "timezone": TIME_ZONE,
        "country": COUNTRY_CODE,
        "city": LAUNCH_CITY,
    }
    return payload


def public_marketplace(request):
    payload = _load_marketplace_data()
    category = request.GET.get("category")
    city = request.GET.get("city")
    budget = request.GET.get("budget")
    q = request.GET.get("q", "").strip().lower()

    experiences = payload.get("experiences", [])
    if category:
        experiences = [item for item in experiences if item.get("category") == category]
    if city:
        experiences = [item for item in experiences if item.get("city", "").lower() == city.lower()]
    if budget:
        try:
            budget_value = int(budget)
            experiences = [item for item in experiences if item.get("price_minor", 0) <= budget_value]
        except ValueError:
            pass
    if q:
        experiences = [
            item
            for item in experiences
            if q in item.get("title", "").lower()
            or q in item.get("summary", "").lower()
            or q in item.get("city", "").lower()
        ]

    return JsonResponse(
        {
            "site": payload.get("site", {}),
            "categories": payload.get("categories", []),
            "experiences": experiences,
            "companions": payload.get("companions", []),
            "collections": payload.get("collections", []),
        }
    )
