import threading
from dataclasses import dataclass, field
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.models.signals import pre_delete

from ingest.adapters.orm.models import Article, Feed, RunRecord
from ingest.adapters.orm.stores import (
    DjangoArticleStore,
    DjangoFeedCatalog,
    DjangoRunLog,
)
from ingest.adapters.postgres_lock import PostgresPassLock
from ingest.application.feed_commands import (
    FeedCommands,
    FeedDeleted,
    FeedDeleteRefused,
)
from ingest.application.ingest_pass import IngestPass
from ingest.domain.article import CanonicalUrl, NewArticle
from ingest.domain.feed import FeedRuleReason, FetchFailure, ParsedFeed
from tests.fakes import FixedClock, feed_items

WAIT_SECONDS = 10


@dataclass
class _ArticleWriter:
    """Stores one article in its own connection and commits when told to."""

    feed_id: int
    inserted: threading.Event = field(default_factory=threading.Event)
    commit: threading.Event = field(default_factory=threading.Event)
    stored: bool | None = None

    def run(self) -> None:
        try:
            with transaction.atomic():
                DjangoArticleStore().add(
                    NewArticle(
                        feed_id=self.feed_id,
                        canonical_url=CanonicalUrl.from_link("https://example.com/a"),
                        title="First article",
                        published_at=None,
                        stored_at=FixedClock().at,
                    )
                )
                self.inserted.set()
                self.commit.wait(WAIT_SECONDS)
            self.stored = True
        except IntegrityError:
            self.stored = False
        finally:
            connection.close()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("delete_commits_first", [True, False])
def test_r10_delete_and_first_article_at_once_one_fails(
    delete_commits_first: bool,
) -> None:
    feed = Feed.objects.create(name="Batch", url="https://batch.test/feed")
    writer = _ArticleWriter(feed_id=feed.id)
    thread = threading.Thread(target=writer.run)
    if not delete_commits_first:
        writer.commit.set()
    thread.start()
    assert writer.inserted.wait(WAIT_SECONDS)
    if not delete_commits_first:
        thread.join(WAIT_SECONDS)

    try:
        result = FeedCommands(DjangoFeedCatalog()).delete(feed.id)
    finally:
        writer.commit.set()
        thread.join(WAIT_SECONDS)

    deleted = result == FeedDeleted(feed.id)
    assert [deleted, writer.stored].count(True) == 1
    feeds, articles = Feed.objects.count(), Article.objects.count()
    assert (feeds, articles) in {(0, 0), (1, 1)}


@pytest.mark.django_db(transaction=True)
def test_r10_article_committed_after_the_delete_check_refuses_the_delete() -> None:
    feed = Feed.objects.create(name="Batch", url="https://batch.test/feed")
    writer = _ArticleWriter(feed_id=feed.id)
    thread = threading.Thread(target=writer.run)
    thread.start()
    assert writer.inserted.wait(WAIT_SECONDS)

    def _commit_article(**_: Any) -> None:
        writer.commit.set()
        thread.join(WAIT_SECONDS)

    pre_delete.connect(_commit_article, sender=Feed)
    try:
        result = FeedCommands(DjangoFeedCatalog()).delete(feed.id)
    finally:
        pre_delete.disconnect(_commit_article, sender=Feed)
        writer.commit.set()
        thread.join(WAIT_SECONDS)

    assert result == FeedDeleteRefused(feed.id, FeedRuleReason.HAS_ARTICLES)
    assert writer.stored is True
    assert (Feed.objects.count(), Article.objects.count()) == (1, 1)


@dataclass
class _DeletingReader:
    """Deletes `doomed_id` while it reads `doomed_url`, then returns the items."""

    doomed_id: int
    doomed_url: str
    results: dict[str, ParsedFeed] = field(default_factory=dict)

    def read(self, url: str) -> ParsedFeed | FetchFailure:
        if url == self.doomed_url:
            assert FeedCommands(DjangoFeedCatalog()).delete(self.doomed_id) == (
                FeedDeleted(self.doomed_id)
            )
        return self.results[url]


@pytest.mark.django_db(transaction=True)
def test_r10_feed_deleted_mid_pass_counts_failed_and_the_pass_completes() -> None:
    doomed = Feed.objects.create(name="Batch", url="https://batch.test/feed")
    next_feed = Feed.objects.create(name="OpenAI", url="https://openai.test/rss")
    reader = _DeletingReader(doomed_id=doomed.id, doomed_url=doomed.url)
    reader.results[doomed.url] = feed_items(doomed.id, 1)
    reader.results[next_feed.url] = feed_items(next_feed.id, 1)

    IngestPass(
        catalog=DjangoFeedCatalog(),
        reader=reader,
        store=DjangoArticleStore(),
        lock=PostgresPassLock(),
        run_log=DjangoRunLog(),
        clock=FixedClock(),
    ).run()

    assert list(Article.objects.values_list("feed_id", flat=True)) == [next_feed.id]
    record = RunRecord.objects.get()
    assert record.finished_at == FixedClock().at
    assert (record.feeds_ok, record.feeds_failed, record.articles_new) == (1, 1, 1)
    assert not Feed.objects.filter(id=doomed.id).exists()
