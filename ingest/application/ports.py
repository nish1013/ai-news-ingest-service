"""Ports the use cases call. Adapters implement them."""

from datetime import datetime
from typing import Protocol

from ingest.domain.article import NewArticle
from ingest.domain.feed import Feed, FeedDetails, FetchFailure, ParsedFeed
from ingest.domain.run import RunCounts


class FeedCatalog(Protocol):
    """The registered feeds."""

    def active_feeds(self) -> list[Feed]:
        """Return the active feeds."""
        ...

    def add(self, details: FeedDetails) -> int:
        """Store an active feed and return its id. Raise FeedRuleError(url_taken)."""
        ...

    def update(self, feed_id: int, details: FeedDetails) -> None:
        """Store a new name and URL. Raise FeedRuleError(url_taken)."""
        ...

    def set_active(self, feed_id: int, *, active: bool) -> None:
        """Store the active flag of a feed."""
        ...

    def delete(self, feed_id: int) -> None:
        """Remove a feed. Raise FeedRuleError(has_articles)."""
        ...


class FeedReader(Protocol):
    """Reads one feed URL from its publisher."""

    def read(self, url: str) -> ParsedFeed | FetchFailure:
        """Return the parsed items, or the reason the read failed."""
        ...


class ArticleStore(Protocol):
    """The stored articles."""

    def add(self, article: NewArticle) -> bool:
        """Store one article. Return False when its canonical URL is stored."""
        ...


class PassLock(Protocol):
    """Lets one ingest pass run at a time."""

    def acquire(self) -> None:
        """Take the lock."""
        ...

    def release(self) -> None:
        """Free the lock."""
        ...


class RunLog(Protocol):
    """The run records of ingest passes."""

    def start(self, started_at: datetime) -> int:
        """Open a run record and return its id."""
        ...

    def finish(self, run_id: int, counts: RunCounts, finished_at: datetime) -> None:
        """Close a run record with the counts of the pass."""
        ...


class Clock(Protocol):
    """The current time."""

    def now(self) -> datetime:
        """Return the current time, zone-aware."""
        ...
