from hashlib import sha256

import pytest

from ingest.adapters.orm.models import Article, Feed, RunRecord
from ingest.adapters.orm.stores import (
    DjangoArticleStore,
    DjangoFeedCatalog,
    DjangoRunLog,
)
from ingest.adapters.postgres_lock import PostgresPassLock
from ingest.application.ingest_pass import IngestPass, PassReport
from ingest.domain.article import (
    ArticleStored,
    CanonicalUrl,
    DuplicateArticleSkipped,
)
from ingest.domain.feed import FeedItem, FetchFailure, ParsedFeed
from tests.fakes import PUBLISHED, FixedClock, StubFeedReader, feed_items
from tests.integration.lock_probe import pass_lock_is_free


def _run(reader: StubFeedReader) -> PassReport:
    return IngestPass(
        catalog=DjangoFeedCatalog(),
        reader=reader,
        store=DjangoArticleStore(),
        lock=PostgresPassLock(),
        run_log=DjangoRunLog(),
        clock=FixedClock(),
    ).run()


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
        reader.results[feed.url] = feed_items(feed.id, 3 if n <= 4 else 2)
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


@pytest.mark.django_db
def test_s6_ac2_copy_from_another_feed_is_skipped_and_the_first_keeps_its_title() -> (
    None
):
    first = Feed.objects.create(name="The Batch", url="https://batch.test/feed")
    second = Feed.objects.create(name="Mirror", url="https://mirror.test/feed")
    reader = StubFeedReader()
    reader.results[first.url] = _one_item("https://example.com/gpt-6", "GPT-6 is out")
    reader.results[second.url] = _one_item("https://example.com/gpt-6/", "Mirror copy")

    report = _run(reader)

    url = CanonicalUrl("https://example.com/gpt-6")
    assert report.articles == (ArticleStored(url), DuplicateArticleSkipped(url))
    assert report.counts.articles_new == 1
    article = Article.objects.get()
    assert (article.feed_id, article.title) == (first.id, "GPT-6 is out")


@pytest.mark.django_db
def test_s6_ac3_same_link_twice_in_one_body_stores_once_and_skips_once() -> None:
    feed = Feed.objects.create(name="The Batch", url="https://batch.test/feed")
    reader = StubFeedReader()
    item = FeedItem(link="https://example.com/a", title="A", published_at=PUBLISHED)
    reader.results[feed.url] = ParsedFeed(items=(item, item))

    report = _run(reader)

    url = CanonicalUrl("https://example.com/a")
    assert report.articles == (ArticleStored(url), DuplicateArticleSkipped(url))
    assert Article.objects.count() == 1


@pytest.mark.django_db
def test_r7_long_link_is_stored_and_the_pass_continues() -> None:
    feed = Feed.objects.create(name="The Batch", url="https://batch.test/feed")
    long_link = _long_link(5000)
    reader = StubFeedReader()
    reader.results[feed.url] = ParsedFeed(
        items=tuple(
            FeedItem(link=link, title="T", published_at=PUBLISHED)
            for link in (long_link, long_link, "https://example.com/next")
        )
    )

    report = _run(reader)

    long_url = CanonicalUrl(long_link)
    assert report.articles == (
        ArticleStored(long_url),
        DuplicateArticleSkipped(long_url),
        ArticleStored(CanonicalUrl("https://example.com/next")),
    )
    assert Article.objects.filter(canonical_url=long_link).exists()
    assert Article.objects.count() == 2


def _long_link(length: int) -> str:
    prefix = "https://example.com/"
    digests = "".join(sha256(str(n).encode()).hexdigest() for n in range(length // 64))
    return prefix + digests[: length - len(prefix)]


def _one_item(link: str, title: str) -> ParsedFeed:
    return ParsedFeed(items=(FeedItem(link=link, title=title, published_at=PUBLISHED),))
