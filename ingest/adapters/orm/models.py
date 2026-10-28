"""Django models for feeds, articles and run records."""

from django.db import models


class Feed(models.Model):
    """A registered feed."""

    name = models.CharField(max_length=200)
    url = models.CharField(max_length=2000)
    active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class Article(models.Model):
    """A stored article."""

    feed = models.ForeignKey(Feed, on_delete=models.PROTECT, related_name="articles")
    canonical_url = models.CharField(max_length=2000)
    title = models.TextField()
    published_at = models.DateTimeField(null=True)
    stored_at = models.DateTimeField(auto_now_add=True)


class RunRecord(models.Model):
    """The record of one ingest pass. No finished time reads as unfinished."""

    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True)
    feeds_ok = models.PositiveIntegerField(default=0)
    feeds_failed = models.PositiveIntegerField(default=0)
    articles_new = models.PositiveIntegerField(default=0)
