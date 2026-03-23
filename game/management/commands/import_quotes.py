import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from game.models import Episode, Quote


class Command(BaseCommand):
    help = "Import quotes from a CSV with columns episode_title, airdate, line."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            type=str,
            default=None,
            help="Path to CSV (default: DATA_CSV_PATH from settings).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Number of Quote rows per bulk_create batch.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all quotes and episodes before import.",
        )

    def handle(self, *args, **options):
        raw_path = options["csv"] or str(settings.DATA_CSV_PATH)
        path = Path(raw_path)
        if not path.is_file():
            raise CommandError(f"CSV not found: {path}")

        batch_size = max(1, int(options["batch_size"]))

        with transaction.atomic():
            if options["clear"]:
                Quote.objects.all().delete()
                Episode.objects.all().delete()

            episode_cache: dict[tuple[str, str], int] = {}
            batch: list[Quote] = []
            total_quotes = 0

            with path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(
                    f,
                    fieldnames=("episode_title", "airdate", "line"),
                )
                for row in reader:
                    title = (row.get("episode_title") or "").strip()
                    airdate = (row.get("airdate") or "").strip()
                    line = (row.get("line") or "").strip()
                    if not title or not line:
                        continue

                    key = (title, airdate)
                    eid = episode_cache.get(key)
                    if eid is None:
                        ep, _ = Episode.objects.get_or_create(
                            title=title,
                            airdate=airdate,
                        )
                        episode_cache[key] = ep.pk
                        eid = ep.pk

                    batch.append(Quote(episode_id=eid, text=line))
                    if len(batch) >= batch_size:
                        Quote.objects.bulk_create(batch, batch_size=batch_size)
                        total_quotes += len(batch)
                        batch = []

                if batch:
                    Quote.objects.bulk_create(batch, batch_size=batch_size)
                    total_quotes += len(batch)

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {total_quotes} quotes ({len(episode_cache)} episodes)."
            )
        )
