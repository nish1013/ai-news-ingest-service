"""Read queries over the article table. The on-time and excluded rules live here."""

from datetime import datetime

from django.db.models import Count, F, Q, QuerySet

from ingest.adapters.orm.models import Article
from ingest.domain.metric import FUTURE_DATE_TOLERANCE, ON_TIME_LIMIT, OnTimeMetric

_EXCLUDED = Q(published_at__isnull=True) | Q(
    published_at__gt=F("stored_at") + FUTURE_DATE_TOLERANCE
)
_ON_TIME = ~_EXCLUDED & Q(stored_at__lt=F("published_at") + ON_TIME_LIMIT)


def on_time_articles() -> QuerySet[Article]:
    """Return the articles stored under ON_TIME_LIMIT after their published date."""
    return Article.objects.filter(_ON_TIME)


def on_time_metric(since: datetime) -> OnTimeMetric:
    """Return the metric over the articles stored at or after `since`."""
    counts = Article.objects.filter(stored_at__gte=since).aggregate(
        total=Count("pk"),
        excluded=Count("pk", filter=_EXCLUDED),
        on_time=Count("pk", filter=_ON_TIME),
    )
    return OnTimeMetric(
        on_time=counts["on_time"],
        counted=counts["total"] - counts["excluded"],
        excluded=counts["excluded"],
        duplicate_urls=_duplicate_url_count(),
    )


def _duplicate_url_count() -> int:
    return (
        Article.objects.values("canonical_url")
        .annotate(rows=Count("pk"))
        .filter(rows__gt=1)
        .count()
    )
