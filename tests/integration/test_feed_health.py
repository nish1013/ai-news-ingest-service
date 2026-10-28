from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from django.db import connection

from ingest.adapters.orm.models import Article, Feed, RunRecord
from ingest.adapters.orm.stores import (
    DjangoArticleStore,
    DjangoFeedCatalog,
    DjangoRunLog,
)
from ingest.adapters.postgres_lock import PostgresPassLock
from ingest.application.ingest_pass import IngestPass
from ingest.domain.feed import FetchFailure
from tests.fakes import FixedClock, StubFeedReader, feed_items

OCT26_0915 = datetime(2026, 10, 26, 9, 15, tzinfo=UTC)
OCT26_0930 = datetime(2026, 10, 26, 9, 30, tzinfo=UTC)
OCT29_1000 = datetime(2026, 10, 29, 10, 0, tzinfo=UTC)
OPENAI_URL = "https://openai.com/blog/rss.xml"
REFUSE_ARTICLE_COMMIT = """
    CREATE FUNCTION refuse_article() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION 'article refused' USING ERRCODE = 'check_violation';
    END $$;
    CREATE CONSTRAINT TRIGGER refuse_article AFTER INSERT ON ingest_article
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION refuse_article();
"""
ALLOW_ARTICLE_COMMIT = """
    DROP TRIGGER refuse_article ON ingest_article;
    DROP FUNCTION refuse_article();
"""


def _run_at(at: datetime, reader: StubFeedReader) -> None:
    IngestPass(
        catalog=DjangoFeedCatalog(),
        reader=reader,
        store=DjangoArticleStore(),
        lock=PostgresPassLock(),
        run_log=DjangoRunLog(),
        clock=FixedClock(at),
    ).run()


def _health(feed: Feed) -> tuple[str, datetime | None, datetime | None]:
    feed.refresh_from_db()
    return feed.last_status, feed.last_read_at, feed.failing_since


@pytest.mark.django_db
def test_s5_ac7_first_failure_sets_failing_since_to_the_read_time() -> None:
    feed = Feed.objects.create(
        name="OpenAI blog", url=OPENAI_URL, last_status="ok", last_read_at=OCT26_0915
    )
    reader = StubFeedReader(results={OPENAI_URL: FetchFailure.timeout()})

    _run_at(OCT26_0915, reader)

    assert _health(feed) == ("fetch_failed", OCT26_0915, OCT26_0915)


@pytest.mark.django_db
def test_s5_ac8_later_failure_keeps_failing_since() -> None:
    feed = Feed.objects.create(
        name="OpenAI blog",
        url=OPENAI_URL,
        last_status="fetch_failed",
        last_read_at=OCT26_0915,
        failing_since=OCT26_0915,
    )
    reader = StubFeedReader(results={OPENAI_URL: FetchFailure.timeout()})

    _run_at(OCT26_0930, reader)

    assert _health(feed) == ("fetch_failed", OCT26_0930, OCT26_0915)


@pytest.mark.django_db
def test_s5_ac9_success_clears_failing_since_and_sets_ok() -> None:
    feed = Feed.objects.create(
        name="OpenAI blog",
        url=OPENAI_URL,
        last_status="fetch_failed",
        last_read_at=OCT26_0930,
        failing_since=OCT26_0915,
    )
    reader = StubFeedReader(results={OPENAI_URL: feed_items(feed.id, 1)})

    _run_at(OCT29_1000, reader)

    assert _health(feed) == ("ok", OCT29_1000, None)


@pytest.mark.django_db
def test_r11_health_update_leaves_name_url_and_active_as_they_are() -> None:
    feed = Feed.objects.create(name="OpenAI blog", url=OPENAI_URL, active=True)
    reader = StubFeedReader(results={OPENAI_URL: FetchFailure.parse()})

    _run_at(OCT26_0915, reader)

    feed.refresh_from_db()
    assert (feed.name, feed.url, feed.active) == ("OpenAI blog", OPENAI_URL, True)
    assert _health(feed) == ("parse_failed", OCT26_0915, OCT26_0915)


@pytest.fixture
def article_commit_refused(transactional_db: None) -> Iterator[None]:
    with connection.cursor() as cursor:
        cursor.execute(REFUSE_ARTICLE_COMMIT)
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute(ALLOW_ARTICLE_COMMIT)


@pytest.mark.django_db(transaction=True)
def test_d21_refused_batch_writes_no_ok_health_for_its_feed(
    article_commit_refused: None,
) -> None:
    feed = Feed.objects.create(
        name="OpenAI blog",
        url=OPENAI_URL,
        last_status="fetch_failed",
        last_read_at=OCT26_0930,
        failing_since=OCT26_0915,
    )
    reader = StubFeedReader(results={OPENAI_URL: feed_items(feed.id, 1)})

    _run_at(OCT29_1000, reader)

    assert _health(feed) == ("fetch_failed", OCT26_0930, OCT26_0915)
    assert not Article.objects.exists()
    record = RunRecord.objects.get()
    assert (record.feeds_ok, record.feeds_failed) == (0, 1)
