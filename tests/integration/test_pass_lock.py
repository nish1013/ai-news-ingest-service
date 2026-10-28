import threading
from dataclasses import dataclass, field
from io import StringIO

import psycopg
import pytest
from django.core.management import call_command
from django.db import connection

from ingest.adapters.orm.models import Feed, RunRecord
from ingest.adapters.orm.stores import (
    DjangoArticleStore,
    DjangoFeedCatalog,
    DjangoRunLog,
)
from ingest.adapters.postgres_lock import PostgresPassLock
from ingest.application.ingest_pass import IngestPass, IngestPassSkipped, PassReport
from ingest.application.ports import FeedReader
from ingest.domain.feed import FetchFailure, ParsedFeed
from tests.fakes import FixedClock, StubFeedReader
from tests.integration.lock_probe import other_session, take_pass_lock

WAIT_SECONDS = 10


@pytest.fixture
def no_endless_lock_wait() -> None:
    # A waiting pass fails instead of hanging. The test transaction undoes the SET.
    with connection.cursor() as cursor:
        cursor.execute("SET lock_timeout = '2s'")


@dataclass
class _HoldingReader:
    """Keeps the pass inside its feed read until told to go on."""

    go_on: threading.Event = field(default_factory=threading.Event)

    def read(self, url: str) -> ParsedFeed | FetchFailure:
        self.go_on.wait(WAIT_SECONDS)
        return ParsedFeed(items=())


def _ingest_pass(reader: FeedReader) -> IngestPass:
    return IngestPass(
        catalog=DjangoFeedCatalog(),
        reader=reader,
        store=DjangoArticleStore(),
        lock=PostgresPassLock(),
        run_log=DjangoRunLog(),
        clock=FixedClock(),
    )


@pytest.mark.django_db
def test_s4_ac2_lock_held_pass_is_skipped_with_one_line_and_no_run_record(
    no_endless_lock_wait: None,
) -> None:
    feed = Feed.objects.create(name="The Batch", url="https://batch.test/feed")
    out = StringIO()

    with other_session() as other:
        assert take_pass_lock(other)
        call_command("ingest_feeds", stdout=out)

    assert out.getvalue() == "Pass skipped: another pass holds the lock\n"
    assert not RunRecord.objects.exists()
    feed.refresh_from_db()
    assert feed.last_read_at is None


@pytest.mark.django_db(transaction=True)
def test_s4_ac3_two_ticks_at_once_one_pass_starts_one_is_skipped() -> None:
    Feed.objects.create(name="The Batch", url="https://batch.test/feed")
    reader = _HoldingReader()
    both_ready = threading.Barrier(2)
    one_done = threading.Semaphore(0)
    results: list[PassReport | IngestPassSkipped] = []

    def tick() -> None:
        try:
            both_ready.wait(WAIT_SECONDS)
            results.append(_ingest_pass(reader).run())
            one_done.release()
        finally:
            connection.close()

    ticks = [threading.Thread(target=tick) for _ in range(2)]
    for thread in ticks:
        thread.start()
    one_done.acquire(timeout=WAIT_SECONDS)
    reader.go_on.set()
    for thread in ticks:
        thread.join(WAIT_SECONDS)

    assert sorted(type(result).__name__ for result in results) == [
        "IngestPassSkipped",
        "PassReport",
    ]
    assert RunRecord.objects.count() == 1


@pytest.mark.django_db
def test_s4_ac4_dead_session_frees_the_lock_and_the_next_pass_starts(
    no_endless_lock_wait: None,
) -> None:
    with other_session() as other:
        assert take_pass_lock(other)
        assert isinstance(_ingest_pass(StubFeedReader()).run(), IngestPassSkipped)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_terminate_backend(%s, %s)", [other.info.backend_pid, 5000]
            )
        with pytest.raises(psycopg.OperationalError):
            other.execute("SELECT 1")

    assert isinstance(_ingest_pass(StubFeedReader()).run(), PassReport)
    assert RunRecord.objects.count() == 1
