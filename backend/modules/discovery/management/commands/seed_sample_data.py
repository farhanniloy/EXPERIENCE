import json
from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed sample public marketplace data for public pages and search experiences."

    def handle(self, *args, **options):
        fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "public_data.json"
        fixture_path.parent.mkdir(parents=True, exist_ok=True)

        with fixture_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)

        self.stdout.write(self.style.SUCCESS(f"Loaded {len(data.get('experiences', []))} experiences and {len(data.get('companions', []))} companions."))
