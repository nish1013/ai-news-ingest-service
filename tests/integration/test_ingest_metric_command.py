from datetime import UTC, datetime, time, timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection

from ingest.adapters.orm.models import ARTICLE_URL_UNIQUE, Article, Feed

YESTERDAY = datetime.now(UTC).date() - timedelta(days=1)
STORED = datetime.combine(YESTERDAY, time(9, 5), tzinfo=UTC)


def store(*published_offsets: timedelta | None, stored_at: datetime = STORED) -> None:
    feed, _ = Feed.objects.get_or_create(name="Batch", url="https://batch.test/feed")
    start = Article.objects.count()
    Article.objects.bulk_create(
        Article(
            feed=feed,
            canonical_url=f"https://example.com/{start + n}",
            title=f"Post {n}",
            published_at=None if offset is None else stored_at - offset,
            stored_at=stored_at,
        )
        for n, offset in enumerate(published_offsets)
    )


def metric(days: int = 14) -> list[str]:
    out = StringIO()
    call_command("ingest_metric", days=days, stdout=out)
    return out.getvalue().splitlines()


@pytest.mark.django_db
def test_s9_ac1_1200_articles_print_on_time_1150_of_1186_excluded_14() -> None:
    store(
        *[timedelta(minutes=10)] * 1150,
        *[timedelta(minutes=45)] * 36,
        *[None] * 14,
    )

    assert metric() == [
        "on time 1,150 of 1,186 = 97.0%, excluded 14",
        "duplicate canonical URLs: 0",
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("minutes", "on_time"), [(29, 1), (30, 0), (31, 0)], ids=["29", "30", "31"]
)
def test_s9_ac1_stored_30_min_or_more_after_published_is_not_on_time(
    minutes: int, on_time: int
) -> None:
    store(timedelta(minutes=minutes))

    assert metric()[0] == f"on time {on_time} of 1 = {on_time * 100}.0%, excluded 0"


@pytest.mark.django_db
def test_s9_ac1_article_stored_before_the_window_is_not_counted() -> None:
    store(timedelta(minutes=10), stored_at=STORED - timedelta(days=14))
    store(timedelta(minutes=45))

    assert metric(days=14)[0] == "on time 0 of 1 = 0.0%, excluded 0"


@pytest.mark.django_db
def test_s9_ac1_empty_window_prints_no_percentage() -> None:
    assert metric()[0] == "on time 0 of 0 = n/a, excluded 0"


@pytest.mark.django_db
def test_s9_ac1_over_5_percent_excluded_prints_the_metric_is_invalid() -> None:
    store(*[timedelta(minutes=10)] * 18, None, None)

    assert metric() == [
        "on time 18 of 18 = 100.0%, excluded 2",
        "duplicate canonical URLs: 0",
        "WARNING: excluded 2 of 20 articles is over 5%. The metric is not valid.",
    ]


@pytest.mark.django_db
def test_s9_ac1_exactly_5_percent_excluded_prints_no_warning() -> None:
    store(*[timedelta(minutes=10)] * 19, None)

    assert len(metric()) == 2


@pytest.mark.django_db
def test_s9_ac2_published_1200_stored_0905_is_excluded() -> None:
    noon = datetime.combine(YESTERDAY, time(12, 0), tzinfo=UTC)
    store(STORED - noon)

    assert metric()[0] == "on time 0 of 0 = n/a, excluded 1"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("ahead", "excluded"),
    [(timedelta(minutes=5), 0), (timedelta(minutes=5, seconds=1), 1)],
    ids=["5min", "5min1s"],
)
def test_s9_ac2_published_more_than_5_min_after_stored_is_excluded(
    ahead: timedelta, excluded: int
) -> None:
    store(-ahead)

    assert metric()[0].endswith(f"excluded {excluded}")


@pytest.mark.django_db
def test_s9_ac3_store_with_articles_prints_0_duplicate_canonical_urls() -> None:
    store(timedelta(minutes=10), timedelta(minutes=45), None)

    assert metric()[1] == "duplicate canonical URLs: 0"


@pytest.mark.django_db
def test_s9_ac3_two_rows_on_one_url_without_the_unique_key_count_as_1() -> None:
    constraint = next(
        c for c in Article._meta.constraints if c.name == ARTICLE_URL_UNIQUE
    )
    with connection.schema_editor() as editor:
        editor.remove_constraint(Article, constraint)
    store(timedelta(minutes=10), timedelta(minutes=10))
    Article.objects.update(canonical_url="https://example.com/same")

    assert metric()[1] == "duplicate canonical URLs: 1"
