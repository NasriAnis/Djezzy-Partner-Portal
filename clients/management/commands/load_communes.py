import json
from django.core.management.base import BaseCommand
from clients.models import Commune


class Command(BaseCommand):
    help = "Loads communes data from a JSON file into the database"

    def add_arguments(self, parser):
        parser.add_argument("json_path", type=str)

    def handle(self, *args, **options):
        json_path = options["json_path"]

        # Clear existing records to prevent duplicates
        Commune.objects.all().delete()

        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        communes_to_create = [
            Commune(
                wilaya_code=str(c.get("wilaya_code", "")).zfill(2),
                name=c.get("commune_name_ascii", c.get("commune_name", "")),
            )
            for c in data
        ]

        Commune.objects.bulk_create(communes_to_create)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully loaded {Commune.objects.count()} communes."
            )
        )
