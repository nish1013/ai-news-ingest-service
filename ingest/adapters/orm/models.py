"""Django models for feeds, articles and run records."""

from django.db import models
from django.db.models.functions import MD5

FEED_URL_UNIQUE = "feed_url_unique"
ARTICLE_URL_UNIQUE = "article_canonical_url_unique"


class Feed(models.Model):
    """A registered feed. Its URL is unique, compared exactly (R9)."""

    name = models.CharField(max_length=200)
    url = models.CharField(max_length=2000)
    active = models.BooleanField(default=True)
    last_status = models.CharField(max_length=20, blank=True, default="")
    last_read_at = models.DateTimeField(null=True, blank=True)
    failing_since = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["url"], name=FEED_URL_UNIQUE),
        ]

    def __str__(self) -> str:
        return self.name


class Article(models.Model):
    """A stored article. One row per canonical URL (R6).

    The key is on the MD5 of the URL: a btree entry holds at most 2704 bytes.
    """

    feed = models.ForeignKey(Feed, on_delete=models.PROTECT, related_name="articles")
    canonical_url = models.TextField()
    title = models.TextField()
    published_at = models.DateTimeField(null=True)
    stored_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(MD5("canonical_url"), name=ARTICLE_URL_UNIQUE),
        ]


class RunRecord(models.Model):
    """The record of one ingest pass. No finished time reads as unfinished."""

    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True)
    feeds_ok = models.PositiveIntegerField(default=0)
    feeds_failed = models.PositiveIntegerField(default=0)
    articles_new = models.PositiveIntegerField(default=0)
