"""ORM adapters for the FeedCatalog, ArticleStore and RunLog ports."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

import psycopg
from django.db import IntegrityError, transaction

from ingest.adapters.orm import models
from ingest.domain.article import NewArticle
from ingest.domain.feed import Feed, FeedDetails, FeedRuleError, FeedRuleReason
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
        with _url_taken_as_rule_error():
            return models.Feed.objects.create(
                name=details.name, url=details.url.value
            ).id

    def update(self, feed_id: int, details: FeedDetails) -> None:
        """Store a new name and URL. Raise FeedRuleError(url_taken)."""
        with _url_taken_as_rule_error():
            models.Feed.objects.filter(id=feed_id).update(
                name=details.name, url=details.url.value
            )


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


@contextmanager
def _url_taken_as_rule_error() -> Iterator[None]:
    try:
        with transaction.atomic():
            yield
    except IntegrityError as err:
        cause = err.__cause__
        if (
            isinstance(cause, psycopg.errors.UniqueViolation)
            and cause.diag.constraint_name == models.FEED_URL_UNIQUE
        ):
            raise FeedRuleError(FeedRuleReason.URL_TAKEN) from err
        raise
