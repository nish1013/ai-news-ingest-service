import threading
import time
from dataclasses import dataclass, field

import pytest
from django.db import connection, transaction

from ingest.adapters.orm.models import Article, Feed
from ingest.adapters.orm.stores import DjangoArticleStore
from ingest.domain.article import CanonicalUrl, NewArticle
from tests.fakes import FixedClock

WAIT_SECONDS = 10
URL = "https://example.com/a"


@dataclass
class _Writer:
    """Stores one article in its own connection. Commits when told to."""

    feed_id: int
    title: str
    inserted: threading.Event = field(default_factory=threading.Event)
    commit: threading.Event = field(default_factory=threading.Event)
    stored: bool | None = None

    def run(self) -> None:
        try:
            with transaction.atomic():
                self.stored = DjangoArticleStore().add(
                    NewArticle(
                        feed_id=self.feed_id,
                        canonical_url=CanonicalUrl.from_link(URL),
                        title=self.title,
                        published_at=None,
                        stored_at=FixedClock().at,
                    )
                )
                self.inserted.set()
                self.commit.wait(WAIT_SECONDS)
        finally:
            connection.close()


@pytest.mark.django_db(transaction=True)
def test_s6_ac4_two_writers_one_url_at_once_unique_key_refuses_the_second() -> None:
    feed = Feed.objects.create(name="Batch", url="https://batch.test/feed")
    first = _Writer(feed_id=feed.id, title="First")
    second = _Writer(feed_id=feed.id, title="Second")
    second.commit.set()
    first_thread = threading.Thread(target=first.run)
    second_thread = threading.Thread(target=second.run)

    first_thread.start()
    assert first.inserted.wait(WAIT_SECONDS)
    second_thread.start()
    try:
        _wait_until_blocked_or_inserted(second)
    finally:
        first.commit.set()
        first_thread.join(WAIT_SECONDS)
        second_thread.join(WAIT_SECONDS)

    assert (first.stored, second.stored) == (True, False)
    assert list(Article.objects.values_list("title", flat=True)) == ["First"]


def _wait_until_blocked_or_inserted(writer: _Writer) -> None:
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline and not writer.inserted.is_set():
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_locks WHERE NOT granted")
            row = cursor.fetchone()
        if row and row[0]:
            return
        writer.inserted.wait(0.01)
