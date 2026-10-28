from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pytest
from django.test import Client

from ingest.adapters.orm.models import Feed, RunRecord
from ingest.adapters.orm.stores import (
    DjangoArticleStore,
    DjangoFeedCatalog,
    DjangoRunLog,
)
from ingest.adapters.postgres_lock import PostgresPassLock
from ingest.application.ingest_pass import IngestPass
from ingest.domain.feed import FetchFailure, ParsedFeed
from tests.fakes import FixedClock, feed_items
from tests.integration.lock_probe import other_session, pass_lock_is_free

RUN_RECORDS_URL = "/admin/ingest/runrecord/"
ARTICLES_PER_FEED = """
    SELECT feed_id, count(*) FROM ingest_article GROUP BY feed_id ORDER BY feed_id
"""


class _ProcessDiedError(BaseException):
    """Stands for a killed process: no handler in the pass catches it."""


@dataclass
class _DyingClock:
    """Raises once it is armed and has answered `calls_left` more times."""

    at: datetime = FixedClock().at
    calls_left: int | None = None

    def now(self) -> datetime:
        if self.calls_left == 0:
            raise _ProcessDiedError
        if self.calls_left is not None:
            self.calls_left -= 1
        return self.at


@dataclass
class _ArmingReader:
    """Arms the clock while it reads `dying_url`."""

    clock: _DyingClock
    dying_url: str
    results: dict[str, ParsedFeed] = field(default_factory=dict)

    def read(self, url: str) -> ParsedFeed | FetchFailure:
        if url == self.dying_url:
            self.clock.calls_left = 1
        return self.results[url]


@pytest.mark.django_db(transaction=True)
def test_s7_ac2_process_dies_after_5_articles_record_stays_open_and_5_stay() -> None:
    batch = Feed.objects.create(name="The Batch", url="https://batch.test/feed")
    openai = Feed.objects.create(name="OpenAI blog", url="https://openai.test/rss")
    clock = _DyingClock()
    reader = _ArmingReader(clock=clock, dying_url=openai.url)
    reader.results[batch.url] = feed_items(batch.id, 5)
    reader.results[openai.url] = feed_items(openai.id, 3)
    ingest_pass = IngestPass(
        catalog=DjangoFeedCatalog(),
        reader=reader,
        store=DjangoArticleStore(),
        lock=PostgresPassLock(),
        run_log=DjangoRunLog(),
        clock=clock,
    )

    with pytest.raises(_ProcessDiedError):
        ingest_pass.run()

    with other_session() as other:
        records = other.execute(
            "SELECT started_at, finished_at FROM ingest_runrecord"
        ).fetchall()
        articles = other.execute(ARTICLES_PER_FEED).fetchall()
    assert records == [(clock.at, None)]
    assert articles == [(batch.id, 5)]
    assert pass_lock_is_free()


@pytest.mark.django_db
def test_s7_ac2_run_records_show_started_finished_counts_and_unfinished(
    admin_client: Client,
) -> None:
    started = FixedClock().at
    RunRecord.objects.create(
        started_at=started,
        finished_at=started + timedelta(minutes=2),
        feeds_ok=19,
        feeds_failed=1,
        articles_new=42,
    )
    RunRecord.objects.create(started_at=started + timedelta(minutes=15))

    response = admin_client.get(RUN_RECORDS_URL)

    assert response.status_code == 200
    rows = [
        (r.started_at, r.finished_at, r.feeds_ok, r.feeds_failed, r.articles_new)
        for r in response.context["cl"].result_list
    ]
    assert rows == [
        (started + timedelta(minutes=15), None, 0, 0, 0),
        (started, started + timedelta(minutes=2), 19, 1, 42),
    ]
    page = response.content.decode()
    assert "Unfinished" in page
    assert (page.count('alt="True"'), page.count('alt="False"')) == (1, 1)
