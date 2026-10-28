"""Read queries over the article table."""

from django.db.models import F, QuerySet

from ingest.adapters.orm.models import Article
from ingest.domain.article import ON_TIME_LIMIT


def on_time_articles() -> QuerySet[Article]:
    """Return the articles stored under ON_TIME_LIMIT after their published date."""
    return Article.objects.filter(
        published_at__isnull=False,
        stored_at__lt=F("published_at") + ON_TIME_LIMIT,
    )
