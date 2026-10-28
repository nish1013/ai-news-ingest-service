from datetime import UTC, datetime

import pytest

from ingest.adapters.orm.models import Article, Feed
from ingest.adapters.orm.stores import (
    DjangoArticleStore,
    DjangoFeedCatalog,
    DjangoRunLog,
)
from ingest.adapters.postgres_lock import PostgresPassLock
from ingest.application.ingest_pass import IngestPass, PassReport
from ingest.domain.article import ArticleStored, CanonicalUrl
from ingest.domain.feed import FeedItem, ParsedFeed
from tests.fakes import FixedClock, StubFeedReader

FETCH_AT = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)


def run_pass_with_one_item(
    published_at: datetime | None, *, now: datetime
) -> PassReport:
    feed = Feed.objects.create(name="The Batch", url="https://batch.test/feed")
    reader = StubFeedReader()
    reader.results[feed.url] = ParsedFeed(
        items=(
            FeedItem(
                link="https://example.com/a", title="A", published_at=published_at
            ),
        )
    )
    return IngestPass(
        catalog=DjangoFeedCatalog(),
        reader=reader,
        store=DjangoArticleStore(),
        lock=PostgresPassLock(),
        run_log=DjangoRunLog(),
        clock=FixedClock(now),
    ).run()


@pytest.mark.django_db
def test_s6_ac9_item_without_published_date_is_stored_with_published_at_empty() -> None:
    report = run_pass_with_one_item(None, now=FETCH_AT)

    assert report.articles == (ArticleStored(CanonicalUrl("https://example.com/a")),)
    article = Article.objects.get()
    assert (article.published_at, article.stored_at) == (None, FETCH_AT)


@pytest.mark.django_db
def test_s6_ac10_future_published_date_is_stored_as_given() -> None:
    noon = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)

    report = run_pass_with_one_item(noon, now=FETCH_AT)

    assert report.articles == (ArticleStored(CanonicalUrl("https://example.com/a")),)
    article = Article.objects.get()
    assert (article.published_at, article.stored_at) == (noon, FETCH_AT)
