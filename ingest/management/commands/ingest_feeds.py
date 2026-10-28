"""Run one ingest pass. Cron starts it each 15 min."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Run one ingest pass over the active feeds."""

    help = "Run one ingest pass over the active feeds."

    def handle(self, *args: object, **options: object) -> None:
        """Run the pass and print its counts."""
        raise NotImplementedError
