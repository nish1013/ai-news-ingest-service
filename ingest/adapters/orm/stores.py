"""ORM adapters for the FeedCatalog, ArticleStore and RunLog ports."""

from datetime import datetime

from ingest.adapters.orm import models
from ingest.domain.article import NewArticle
from ingest.domain.feed import Feed, FeedDetails
from ingest.domain.run import RunCounts


class DjangoFeedCatalog:
    """Feeds from the feed table."""

    def active_feeds(self) -> list[Feed]:
        """Return the active feeds."""
        return [
            Feed(id=row.id, name=row.name, url=row.url)
            for row in models.Feed.objects.filter(active=True).order_by("id")
        ]

    def add(self, details: FeedDetails) -> int:
        """Store an active feed and return its id. Raise FeedRuleError(url_taken)."""
        raise NotImplementedError

    def update(self, feed_id: int, details: FeedDetails) -> None:
        """Store a new name and URL. Raise FeedRuleError(url_taken)."""
        raise NotImplementedError


class DjangoArticleStore:
    """Articles in the article table."""

    def add(self, article: NewArticle) -> None:
        """Store one article."""
        models.Article.objects.create(
            feed_id=article.feed_id,
            canonical_url=article.canonical_url.value,
            title=article.title,
            published_at=article.published_at,
        )


class DjangoRunLog:
    """Run records in the run record table."""

    def start(self, started_at: datetime) -> int:
        """Open a run record and return its id."""
        return models.RunRecord.objects.create(started_at=started_at).id

    def finish(self, run_id: int, counts: RunCounts, finished_at: datetime) -> None:
        """Close a run record with the counts of the pass."""
        models.RunRecord.objects.filter(id=run_id).update(
            finished_at=finished_at,
            feeds_ok=counts.feeds_ok,
            feeds_failed=counts.feeds_failed,
            articles_new=counts.articles_new,
        )
