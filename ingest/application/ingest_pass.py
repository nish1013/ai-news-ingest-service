"""The ingest pass: read each active feed and store its items."""

from dataclasses import dataclass

from ingest.application.ports import (
    ArticleStore,
    Clock,
    FeedCatalog,
    FeedReader,
    PassLock,
    RunLog,
)
from ingest.domain.article import CanonicalUrl, NewArticle
from ingest.domain.feed import Feed, FeedItem, FetchFailure
from ingest.domain.run import RunCounts


@dataclass(frozen=True)
class PassReport:
    """The pass list and the counts of one pass."""

    feeds: tuple[Feed, ...]
    counts: RunCounts


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

    def run(self) -> PassReport:
        """Run one pass and write its run record."""
        self._lock.acquire()
        try:
            return self._run_locked()
        finally:
            self._lock.release()

    def _run_locked(self) -> PassReport:
        feeds = tuple(self._catalog.active_feeds())
        run_id = self._run_log.start(self._clock.now())
        feeds_ok = feeds_failed = articles_new = 0
        for feed in feeds:
            result = self._reader.read(feed.url)
            if isinstance(result, FetchFailure):
                feeds_failed += 1
                continue
            feeds_ok += 1
            for item in result.items:
                self._store.add(_new_article(feed, item))
                articles_new += 1
        counts = RunCounts(
            feeds_ok=feeds_ok, feeds_failed=feeds_failed, articles_new=articles_new
        )
        self._run_log.finish(run_id, counts, self._clock.now())
        return PassReport(feeds=feeds, counts=counts)


def _new_article(feed: Feed, item: FeedItem) -> NewArticle:
    return NewArticle(
        feed_id=feed.id,
        canonical_url=CanonicalUrl.from_link(item.link),
        title=item.title,
        published_at=item.published_at,
    )
