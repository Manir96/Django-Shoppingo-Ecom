from django.core.management.base import BaseCommand
from pathlib import Path
import json
from accounts.models import CountryName  

class Command(BaseCommand):
    help = "Import countries from a JSON file. Supports list of strings or list of {'name':...}."

    def add_arguments(self, parser):
        parser.add_argument('file', type=str, help='Path to countries.json')

    def handle(self, *args, **options):
        path = Path(options['file'])
        if not path.exists():
            self.stdout.write(self.style.ERROR(f"File not found: {path}"))
            return

        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Invalid JSON: {e}"))
            return

        created = 0
        for item in data:
            name = item.get("name") if isinstance(item, dict) else item
            if not name:
                continue
            name = name.strip()
            _, was_created = CountryName.objects.get_or_create(nameName=name)
            if was_created:
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {created} new countries. Total now: {CountryName.objects.count()}"
            )
        )
