"""Run one ingest pass. Cron starts it each 15 min."""

from django.core.management.base import BaseCommand

from ingest.adapters.clock import SystemClock
from ingest.adapters.feed_reader import HttpFeedReader
from ingest.adapters.orm.stores import (
    DjangoArticleStore,
    DjangoFeedCatalog,
    DjangoRunLog,
)
from ingest.adapters.postgres_lock import PostgresPassLock
from ingest.application.ingest_pass import IngestPass, IngestPassSkipped


class Command(BaseCommand):
    """Run one ingest pass over the active feeds."""

    help = "Run one ingest pass over the active feeds."

    def handle(self, *args: object, **options: object) -> None:
        """Run the pass and print its counts."""
        report = IngestPass(
            catalog=DjangoFeedCatalog(),
            reader=HttpFeedReader(),
            store=DjangoArticleStore(),
            lock=PostgresPassLock(),
            run_log=DjangoRunLog(),
            clock=SystemClock(),
        ).run()
        if isinstance(report, IngestPassSkipped):
            self.stdout.write("Pass skipped: another pass holds the lock")
            return
        counts = report.counts
        self.stdout.write(
            f"Pass completed: {counts.feeds_ok} feeds ok, {counts.feeds_failed} "
            f"failed, {counts.articles_new} new articles"
        )
