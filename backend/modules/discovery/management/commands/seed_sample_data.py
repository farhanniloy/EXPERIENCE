import json
from pathlib import Path

from django.core.management.base import BaseCommand

from modules.platform.models import (
    Category,
    CollectionExperience,
    EventCollection,
    Experience,
    ExperienceMedia,
    HostProfile,
    User,
)
from config.product import COUNTRY_CODE, CURRENCY_CODE, TIME_ZONE


class Command(BaseCommand):
    help = "Seed sample public marketplace data for public pages and search experiences."

    def handle(self, *args, **options):
        fixture_path = Path(__file__).resolve().parents[4] / "fixtures" / "public_data.json"
        fixture_path.parent.mkdir(parents=True, exist_ok=True)

        with fixture_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)

        categories = {}
        for item in data.get("categories", []):
            category, _ = Category.objects.update_or_create(
                slug=item["slug"],
                defaults={
                    "name": item["name"],
                    "description": item.get("description", ""),
                    "icon": item.get("icon", ""),
                    "is_active": True,
                    "sort_order": len(categories),
                },
            )
            categories[item["slug"]] = category

        hosts = {}
        for item in data.get("companions", []):
            host_slug = item["slug"]
            email = f"sample+{host_slug}@along.local"
            user = User.objects.filter(email=email).first()
            if user is None:
                user = User.objects.create_user(
                    email=email,
                    password=None,
                    display_name=item["name"],
                    country_code=COUNTRY_CODE,
                    timezone=TIME_ZONE,
                )
            profile, _ = HostProfile.objects.update_or_create(
                user=user.auth_user,
                defaults={
                    "slug": host_slug,
                    "headline": item.get("headline", ""),
                    "biography": item.get("bio", ""),
                    "image": item.get("image", "/placeholder-host.svg"),
                    "city": item.get("city", ""),
                    "country_code": COUNTRY_CODE,
                    "languages": ["English"],
                    "interests": item.get("tags", []),
                    "status": HostProfile.Status.APPROVED,
                    "verified": item.get("verified", False),
                    "average_rating": item.get("rating", 0),
                    "completed_bookings": item.get("completed_bookings", 0),
                },
            )
            hosts[item["name"]] = profile

        experiences = {}
        for item in data.get("experiences", []):
            host = hosts.get(item.get("host_name"))
            if host is None:
                continue
            experience, _ = Experience.objects.update_or_create(
                slug=item["slug"],
                defaults={
                    "host": host,
                    "title": item["title"],
                    "description": item.get("description", ""),
                    "summary": item.get("summary", ""),
                    "duration_minutes": item.get("duration_minutes", 60),
                    "pricing_type": Experience.PricingType.FIXED,
                    "price_minor": item.get("price_minor", 0),
                    "currency": CURRENCY_CODE,
                    "instant_booking_enabled": item.get("instant_book", False),
                    "status": Experience.Status.PUBLISHED,
                    "rating": item.get("rating", 0),
                },
            )
            category = categories.get(item.get("category"))
            if category:
                experience.categories.set([category])
            ExperienceMedia.objects.update_or_create(
                experience=experience,
                object_key=item.get("image", "/placeholder-experience.svg"),
                defaults={
                    "media_type": ExperienceMedia.MediaType.IMAGE,
                    "alt_text": item["title"],
                    "sort_order": 0,
                },
            )
            experiences[item["slug"]] = experience

        for item in data.get("collections", []):
            collection, _ = EventCollection.objects.update_or_create(
                slug=item["slug"],
                defaults={
                    "title": item["title"],
                    "description": item.get("description", ""),
                    "city": item.get("city", ""),
                    "country_code": COUNTRY_CODE,
                    "banner_image": item.get("image", "/placeholder-experience.svg"),
                    "status": EventCollection.Status.ACTIVE,
                },
            )
            for position, experience_slug in enumerate(item.get("experience_ids", [])):
                experience = experiences.get(experience_slug)
                if experience:
                    CollectionExperience.objects.update_or_create(
                        collection=collection,
                        experience=experience,
                        defaults={"sort_order": position},
                    )

        self.stdout.write(
            self.style.SUCCESS(
                "Seeded sample marketplace data: "
                f"{len(categories)} categories, {len(hosts)} hosts, "
                f"{len(experiences)} experiences, and {len(data.get('collections', []))} collections."
            )
        )
