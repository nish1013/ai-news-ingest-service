from datetime import UTC, datetime

import pytest

from ingest.adapters.orm.models import Article, Feed, RunRecord
from ingest.adapters.orm.stores import (
    DjangoArticleStore,
    DjangoFeedCatalog,
    DjangoRunLog,
)
from ingest.adapters.postgres_lock import PostgresPassLock
from ingest.application.ingest_pass import IngestPass
from ingest.domain.feed import FeedItem, FetchFailure, ParsedFeed
from tests.fakes import FixedClock, StubFeedReader
from tests.integration.lock_probe import pass_lock_is_free

PUBLISHED = datetime(2026, 10, 26, 8, 50, tzinfo=UTC)


def _run(reader: StubFeedReader) -> None:
    IngestPass(
        catalog=DjangoFeedCatalog(),
        reader=reader,
        store=DjangoArticleStore(),
        lock=PostgresPassLock(),
        run_log=DjangoRunLog(),
        clock=FixedClock(),
    ).run()


def _items(feed_id: int, count: int) -> ParsedFeed:
    return ParsedFeed(
        items=tuple(
            FeedItem(
                link=f"https://example.com/{feed_id}/{n}",
                title=f"Item {n}",
                published_at=PUBLISHED,
            )
            for n in range(count)
        )
    )


@pytest.mark.django_db
def test_s6_ac1_article_is_stored_with_its_canonical_url() -> None:
    feed = Feed.objects.create(name="The Batch", url="https://batch.test/feed")
    reader = StubFeedReader()
    reader.results[feed.url] = ParsedFeed(
        items=(
            FeedItem(
                link="https://Example.com/gpt-6/?utm_source=rss&id=7#top",
                title="GPT-6 is out",
                published_at=PUBLISHED,
            ),
        )
    )

    _run(reader)

    article = Article.objects.get()
    assert (
        article.feed_id,
        article.canonical_url,
        article.title,
        article.published_at,
    ) == (feed.id, "https://example.com/gpt-6?id=7", "GPT-6 is out", PUBLISHED)


@pytest.mark.django_db
def test_s7_ac1_run_record_holds_counts_and_the_lock_is_free() -> None:
    reader = StubFeedReader()
    for n in range(1, 21):
        feed = Feed.objects.create(name=f"Feed {n}", url=f"https://feed{n}.test/rss")
        reader.results[feed.url] = _items(feed.id, 3 if n <= 4 else 2)
    reader.results["https://feed20.test/rss"] = FetchFailure(reason="timeout")

    _run(reader)

    record = RunRecord.objects.get()
    assert (record.feeds_ok, record.feeds_failed, record.articles_new) == (19, 1, 42)
    assert (record.started_at, record.finished_at) == (
        FixedClock().at,
        FixedClock().at,
    )
    assert Article.objects.count() == 42
    assert pass_lock_is_free()
