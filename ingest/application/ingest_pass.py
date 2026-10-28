"""The ingest pass: read each active feed and store its items."""

from dataclasses import dataclass

from ingest.application.ports import (
    ArticleBatchError,
    ArticleStore,
    Clock,
    FeedCatalog,
    FeedReader,
    PassLock,
    RunLog,
)
from ingest.domain.article import (
    ArticleOutcome,
    ArticleRejected,
    ArticleRuleError,
    ArticleStored,
    CanonicalUrl,
    DuplicateArticleSkipped,
    NewArticle,
)
from ingest.domain.feed import Feed, FeedItem, FetchFailure
from ingest.domain.run import RunCounts


@dataclass(frozen=True)
class PassReport:
    """The pass list, the outcome of each item and the counts of one pass."""

    feeds: tuple[Feed, ...]
    articles: tuple[ArticleOutcome, ...]
    counts: RunCounts


@dataclass(frozen=True)
class IngestPassSkipped:
    """Another pass holds the pass lock. The tick changes no data."""


class IngestPass:
    """Runs one ingest pass under the pass lock."""

    def __init__(
        self,
        *,
        catalog: FeedCatalog,
        reader: FeedReader,
        store: ArticleStore,
        lock: PassLock,
        run_log: RunLog,
        clock: Clock,
    ) -> None:
        self._catalog = catalog
        self._reader = reader
        self._store = store
        self._lock = lock
        self._run_log = run_log
        self._clock = clock

    def run(self) -> PassReport | IngestPassSkipped:
        """Run one pass and write its run record. Skip when another pass runs."""
        if not self._lock.try_acquire():
            return IngestPassSkipped()
        try:
            return self._run_locked()
        finally:
            self._lock.release()

    def _run_locked(self) -> PassReport:
        feeds = tuple(self._catalog.active_feeds())
        run_id = self._run_log.start(self._clock.now())
        feeds_ok = feeds_failed = 0
        articles: list[ArticleOutcome] = []
        for feed in feeds:
            read_at = self._clock.now()
            result = self._reader.read(feed.url)
            self._catalog.save_health(feed.id, feed.health_after(result, read_at))
            if isinstance(result, FetchFailure):
                feeds_failed += 1
                continue
            try:
                with self._store.batch():
                    outcomes = [self._ingest(feed, item) for item in result.items]
            except ArticleBatchError:
                feeds_failed += 1
                continue
            feeds_ok += 1
            articles.extend(outcomes)
        counts = RunCounts(
            feeds_ok=feeds_ok,
            feeds_failed=feeds_failed,
            articles_new=sum(isinstance(a, ArticleStored) for a in articles),
        )
        self._run_log.finish(run_id, counts, self._clock.now())
        return PassReport(feeds=feeds, articles=tuple(articles), counts=counts)

    def _ingest(self, feed: Feed, item: FeedItem) -> ArticleOutcome:
        try:
            canonical_url = CanonicalUrl.from_link(item.link)
        except ArticleRuleError as err:
            return ArticleRejected(item.link, err.reason)
        article = NewArticle(
            feed_id=feed.id,
            canonical_url=canonical_url,
            title=item.title,
            published_at=item.published_at,
            stored_at=self._clock.now(),
        )
        if self._store.add(article):
            return ArticleStored(article.canonical_url)
        return DuplicateArticleSkipped(article.canonical_url)
