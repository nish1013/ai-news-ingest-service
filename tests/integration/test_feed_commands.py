from datetime import UTC, datetime

import pytest

from ingest.adapters.orm.models import Article, Feed
from ingest.adapters.orm.stores import (
    DjangoArticleStore,
    DjangoFeedCatalog,
    DjangoRunLog,
)
from ingest.adapters.postgres_lock import PostgresPassLock
from ingest.application.feed_commands import (
    FeedCommands,
    FeedDeactivated,
    FeedDeleted,
    FeedDeleteRefused,
    FeedEdited,
    FeedReactivated,
    FeedRegistered,
    FeedRejected,
)
from ingest.application.ingest_pass import IngestPass
from ingest.domain.feed import FeedRuleReason, ParsedFeed
from tests.fakes import FixedClock, StubFeedReader

BATCH_URL = "https://www.deeplearning.ai/the-batch/feed/"
OPENAI_URL = "https://openai.com/blog/rss.xml"


def _commands() -> FeedCommands:
    return FeedCommands(DjangoFeedCatalog())


def _feeds() -> list[tuple[str, str]]:
    return list(Feed.objects.order_by("id").values_list("name", "url"))


def _next_pass_reads() -> list[str]:
    reader = StubFeedReader()
    for url in Feed.objects.values_list("url", flat=True):
        reader.results[url] = ParsedFeed(items=())
    report = IngestPass(
        catalog=DjangoFeedCatalog(),
        reader=reader,
        store=DjangoArticleStore(),
        lock=PostgresPassLock(),
        run_log=DjangoRunLog(),
        clock=FixedClock(),
    ).run()
    return [feed.url for feed in report.feeds]


def _add_articles(feed: Feed, count: int) -> None:
    for n in range(count):
        Article.objects.create(
            feed=feed,
            canonical_url=f"{feed.url}/{n}",
            title=f"Post {n}",
            published_at=datetime(2026, 10, 26, 9, 0, tzinfo=UTC),
            stored_at=FixedClock().at,
        )


@pytest.mark.django_db
def test_s1_ac2_ftp_url_is_rejected() -> None:
    result = _commands().register(name="Bad", url="ftp://x.org/feed")

    assert result == FeedRejected(FeedRuleReason.URL_SCHEME)
    assert _feeds() == []


@pytest.mark.django_db
def test_s1_ac3_empty_url_is_rejected() -> None:
    result = _commands().register(name="Empty", url="")

    assert result == FeedRejected(FeedRuleReason.URL_MISSING)
    assert _feeds() == []


@pytest.mark.django_db
def test_s1_ac4_blank_name_is_rejected() -> None:
    result = _commands().register(name="  ", url=BATCH_URL)

    assert result == FeedRejected(FeedRuleReason.NAME_MISSING)
    assert _feeds() == []


@pytest.mark.django_db
def test_s1_ac5_url_of_another_feed_is_rejected() -> None:
    _commands().register(name="The Batch", url=BATCH_URL)

    result = _commands().register(name="Batch", url=BATCH_URL)

    assert result == FeedRejected(FeedRuleReason.URL_TAKEN)
    assert _feeds() == [("The Batch", BATCH_URL)]


@pytest.mark.django_db
def test_s1_ac5_url_compare_is_exact() -> None:
    _commands().register(name="The Batch", url=BATCH_URL)

    result = _commands().register(name="Batch", url=BATCH_URL.upper())

    assert isinstance(result, FeedRegistered)
    assert len(_feeds()) == 2


@pytest.mark.django_db
def test_s2_ac1_new_url_is_stored() -> None:
    feed = Feed.objects.create(name="OpenAI blog", url="https://openai.com/rss")

    result = _commands().edit(feed.id, name="OpenAI blog", url=OPENAI_URL)

    assert result == FeedEdited(feed.id)
    assert _feeds() == [("OpenAI blog", OPENAI_URL)]


@pytest.mark.django_db
def test_s2_ac2_url_with_no_scheme_is_rejected() -> None:
    feed = Feed.objects.create(name="OpenAI blog", url=OPENAI_URL)

    result = _commands().edit(feed.id, name="OpenAI blog", url="openai.com/blog")

    assert result == FeedRejected(FeedRuleReason.URL_SCHEME)
    assert _feeds() == [("OpenAI blog", OPENAI_URL)]


@pytest.mark.django_db
def test_s2_ac3_articles_keep_their_feed_after_a_url_change() -> None:
    feed = Feed.objects.create(name="OpenAI blog", url="https://openai.com/rss")
    _add_articles(feed, 12)

    result = _commands().edit(feed.id, name="OpenAI blog", url=OPENAI_URL)

    assert result == FeedEdited(feed.id)
    assert Article.objects.filter(feed_id=feed.id).count() == 12


@pytest.mark.django_db
def test_s2_ac4_url_of_another_feed_is_rejected() -> None:
    Feed.objects.create(name="The Batch", url=BATCH_URL)
    feed = Feed.objects.create(name="OpenAI blog", url=OPENAI_URL)

    result = _commands().edit(feed.id, name="OpenAI blog", url=BATCH_URL)

    assert result == FeedRejected(FeedRuleReason.URL_TAKEN)
    assert _feeds() == [("The Batch", BATCH_URL), ("OpenAI blog", OPENAI_URL)]


@pytest.mark.django_db
def test_s3_ac1_next_pass_does_not_read_a_deactivated_feed() -> None:
    Feed.objects.create(name="The Batch", url=BATCH_URL)
    feed = Feed.objects.create(name="OpenAI blog", url=OPENAI_URL)

    result = _commands().set_active(feed.id, active=False)

    assert result == FeedDeactivated(feed.id)
    assert _next_pass_reads() == [BATCH_URL]


@pytest.mark.django_db
def test_s3_ac2_next_pass_reads_a_reactivated_feed() -> None:
    Feed.objects.create(name="The Batch", url=BATCH_URL)
    feed = Feed.objects.create(name="OpenAI blog", url=OPENAI_URL, active=False)

    result = _commands().set_active(feed.id, active=True)

    assert result == FeedReactivated(feed.id)
    assert _next_pass_reads() == [BATCH_URL, OPENAI_URL]


@pytest.mark.django_db
def test_s8_ac1_feed_with_no_articles_is_deleted() -> None:
    feed = Feed.objects.create(name="Batch", url=BATCH_URL)

    result = _commands().delete(feed.id)

    assert result == FeedDeleted(feed.id)
    assert _feeds() == []


@pytest.mark.django_db
def test_s8_ac2_feed_with_articles_is_not_deleted() -> None:
    feed = Feed.objects.create(name="OpenAI blog", url=OPENAI_URL)
    _add_articles(feed, 12)

    result = _commands().delete(feed.id)

    assert result == FeedDeleteRefused(feed.id, FeedRuleReason.HAS_ARTICLES)
    assert _feeds() == [("OpenAI blog", OPENAI_URL)]
    assert Article.objects.filter(feed_id=feed.id).count() == 12
