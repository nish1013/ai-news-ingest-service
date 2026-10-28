"""Print the on-time metric of the last N days."""

from argparse import ArgumentParser
from datetime import timedelta

from django.core.management.base import BaseCommand

from ingest.adapters.clock import SystemClock
from ingest.adapters.orm.queries import on_time_metric
from ingest.domain.metric import EXCLUDED_LIMIT_PERCENT


class Command(BaseCommand):
    """Print the on-time metric, the excluded count and the duplicate URL count."""

    help = "Print the on-time metric of the articles stored in the last N days."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add the --days option."""
        parser.add_argument("--days", type=int, default=14)

    def handle(self, *args: object, **options: object) -> None:
        """Read the metric and print it."""
        days = options["days"]
        assert isinstance(days, int)
        metric = on_time_metric(SystemClock().now() - timedelta(days=days))
        percent = "n/a" if metric.percent is None else f"{metric.percent:.1f}%"
        self.stdout.write(
            f"on time {metric.on_time:,} of {metric.counted:,} = {percent}, "
            f"excluded {metric.excluded:,}"
        )
        self.stdout.write(f"duplicate canonical URLs: {metric.duplicate_urls:,}")
        if not metric.valid:
            self.stdout.write(
                f"WARNING: excluded {metric.excluded:,} of {metric.total:,} "
                f"articles is over {EXCLUDED_LIMIT_PERCENT}%. The metric is not valid."
            )
