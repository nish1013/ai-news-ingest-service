from datetime import UTC, datetime

import pytest

from ingest.adapters.orm.models import Article
from ingest.adapters.orm.queries import on_time_articles
from tests.integration.test_article_dates import run_pass_with_one_item


@pytest.mark.django_db
def test_s6_ac7_stored_0910_published_0900_counts_as_stored_under_30_min() -> None:
    run_pass_with_one_item(
        datetime(2026, 10, 26, 9, 0, tzinfo=UTC),
        now=datetime(2026, 10, 26, 9, 10, tzinfo=UTC),
    )

    assert list(on_time_articles()) == [Article.objects.get()]


@pytest.mark.django_db
@pytest.mark.parametrize("stored_minute", [30, 45])
def test_s6_ac7_stored_30_min_or_more_after_published_is_not_on_time(
    stored_minute: int,
) -> None:
    run_pass_with_one_item(
        datetime(2026, 10, 26, 9, 0, tzinfo=UTC),
        now=datetime(2026, 10, 26, 9, stored_minute, tzinfo=UTC),
    )

    assert not on_time_articles().exists()


@pytest.mark.django_db
def test_s6_ac7_article_without_published_date_is_not_on_time() -> None:
    run_pass_with_one_item(None, now=datetime(2026, 10, 26, 9, 10, tzinfo=UTC))

    assert not on_time_articles().exists()
