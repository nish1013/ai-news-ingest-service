import pytest

from ingest.application.ingest_pass import IngestPass
from ingest.domain.article import (
    ArticleRejected,
    ArticleRejectReason,
    ArticleStored,
    CanonicalUrl,
)
from ingest.domain.feed import Feed, FeedItem, FetchFailure, ParsedFeed
from ingest.domain.run import RunCounts
from tests.fakes import (
    PUBLISHED,
    FakePassLock,
    FixedClock,
    InMemoryArticleStore,
    InMemoryFeedCatalog,
    InMemoryRunLog,
    StubFeedReader,
    feed_items,
)


def _pass(
    catalog: InMemoryFeedCatalog,
    reader: StubFeedReader,
    store: InMemoryArticleStore,
    lock: FakePassLock,
    run_log: InMemoryRunLog,
) -> IngestPass:
    return IngestPass(
        catalog=catalog,
        reader=reader,
        store=store,
        lock=lock,
        run_log=run_log,
        clock=FixedClock(),
    )


def test_s4_ac1_pass_list_holds_the_active_feeds() -> None:
    catalog = InMemoryFeedCatalog()
    reader = StubFeedReader()
    for feed_id, active in ((1, True), (2, True), (3, False)):
        url = f"https://example.com/feed/{feed_id}"
        catalog.add(Feed(id=feed_id, url=url), active=active)
        reader.results[url] = feed_items(feed_id, 0)
    run_log = InMemoryRunLog()

    report = _pass(
        catalog, reader, InMemoryArticleStore(), FakePassLock(), run_log
    ).run()

    assert [feed.id for feed in report.feeds] == [1, 2]
    assert reader.read_urls == [
        "https://example.com/feed/1",
        "https://example.com/feed/2",
    ]
    assert run_log.started == [FixedClock().at]


def test_pass_stores_the_feed_id_title_and_published_at() -> None:
    catalog = InMemoryFeedCatalog()
    catalog.add(Feed(id=1, url="https://batch.test/feed"))
    reader = StubFeedReader()
    reader.results["https://batch.test/feed"] = ParsedFeed(
        items=(
            FeedItem(
                link="https://example.com/gpt-6",
                title="GPT-6 is out",
                published_at=PUBLISHED,
            ),
        )
    )
    store = InMemoryArticleStore()

    _pass(catalog, reader, store, FakePassLock(), InMemoryRunLog()).run()

    [article] = store.articles
    assert (article.feed_id, article.title, article.published_at) == (
        1,
        "GPT-6 is out",
        PUBLISHED,
    )


@pytest.mark.parametrize(
    ("link", "reason"),
    [
        ("", ArticleRejectReason.LINK_MISSING),
        ("/news/42", ArticleRejectReason.LINK_NOT_ABSOLUTE),
    ],
    ids=["s6_ac5_no_link", "s6_ac6_relative_link"],
)
def test_s6_ac5_ac6_bad_link_is_rejected_and_the_next_item_is_stored(
    link: str, reason: ArticleRejectReason
) -> None:
    catalog = InMemoryFeedCatalog()
    catalog.add(Feed(id=1, url="https://batch.test/feed"))
    reader = StubFeedReader()
    reader.results["https://batch.test/feed"] = ParsedFeed(
        items=(
            FeedItem(link=link, title="Bad", published_at=PUBLISHED),
            FeedItem(link="https://example.com/b", title="B", published_at=PUBLISHED),
        )
    )
    store = InMemoryArticleStore()

    report = _pass(catalog, reader, store, FakePassLock(), InMemoryRunLog()).run()

    assert report.articles == (
        ArticleRejected(link, reason),
        ArticleStored(CanonicalUrl("https://example.com/b")),
    )
    assert [a.title for a in store.articles] == ["B"]
    assert report.counts.articles_new == 1


def test_s7_ac1_run_record_counts_feeds_and_new_articles_and_frees_the_lock() -> None:
    catalog = InMemoryFeedCatalog()
    reader = StubFeedReader()
    for feed_id in range(1, 21):
        url = f"https://example.com/feed/{feed_id}"
        catalog.add(Feed(id=feed_id, url=url))
        reader.results[url] = feed_items(feed_id, 3 if feed_id <= 4 else 2)
    reader.results["https://example.com/feed/20"] = FetchFailure(reason="timeout")
    store = InMemoryArticleStore()
    lock = FakePassLock()
    run_log = InMemoryRunLog()

    report = _pass(catalog, reader, store, lock, run_log).run()

    expected = RunCounts(feeds_ok=19, feeds_failed=1, articles_new=42)
    assert report.counts == expected
    assert run_log.finished == {1: expected}
    assert len(store.articles) == 42
    assert (lock.acquired, lock.held) == (1, False)
