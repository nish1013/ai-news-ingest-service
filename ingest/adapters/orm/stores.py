"""ORM adapters for the FeedCatalog, ArticleStore and RunLog ports."""

from datetime import datetime

from ingest.domain.article import NewArticle
from ingest.domain.feed import Feed
from ingest.domain.run import RunCounts


class DjangoFeedCatalog:
    """Feeds from the feed table."""

    def active_feeds(self) -> list[Feed]:
        """Return the active feeds."""
        raise NotImplementedError


class DjangoArticleStore:
    """Articles in the article table."""

    def add(self, article: NewArticle) -> None:
        """Store one article."""
        raise NotImplementedError


class DjangoRunLog:
    """Run records in the run record table."""

    def start(self, started_at: datetime) -> int:
        """Open a run record and return its id."""
        raise NotImplementedError

    def finish(self, run_id: int, counts: RunCounts, finished_at: datetime) -> None:
        """Close a run record with the counts of the pass."""
        raise NotImplementedError
