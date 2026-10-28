from datetime import UTC, datetime

import pytest

from ingest.domain.feed import (
    Feed,
    FeedHealth,
    FeedStatus,
    FetchFailure,
    ParsedFeed,
)

OCT26_0915 = datetime(2026, 10, 26, 9, 15, tzinfo=UTC)
OCT26_0930 = datetime(2026, 10, 26, 9, 30, tzinfo=UTC)
OCT29_1000 = datetime(2026, 10, 29, 10, 0, tzinfo=UTC)
URL = "https://openai.com/blog/rss.xml"


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        (FetchFailure.timeout(), "timeout"),
        (FetchFailure.http_status(503), "http_503"),
        (FetchFailure.connection(), "connection"),
        (FetchFailure.too_large(), "too_large"),
        (FetchFailure.parse(), "parse"),
    ],
)
def test_r4_r5_fetch_failure_reasons(failure: FetchFailure, reason: str) -> None:
    assert failure.reason == reason


@pytest.mark.parametrize("reason", ["", "slow", "http_", "http_abc", "http_99"])
def test_r4_fetch_failure_refuses_an_unknown_reason(reason: str) -> None:
    with pytest.raises(ValueError):
        FetchFailure(reason=reason)


@pytest.mark.parametrize(
    ("before", "result", "at", "after"),
    [
        (
            FeedHealth(FeedStatus.OK, OCT26_0915, None),
            FetchFailure.timeout(),
            OCT26_0930,
            FeedHealth(FeedStatus.FETCH_FAILED, OCT26_0930, OCT26_0930),
        ),
        (
            FeedHealth(FeedStatus.FETCH_FAILED, OCT26_0915, OCT26_0915),
            FetchFailure.timeout(),
            OCT26_0930,
            FeedHealth(FeedStatus.FETCH_FAILED, OCT26_0930, OCT26_0915),
        ),
        (
            FeedHealth(FeedStatus.FETCH_FAILED, OCT26_0930, OCT26_0915),
            ParsedFeed(items=()),
            OCT29_1000,
            FeedHealth(FeedStatus.OK, OCT29_1000, None),
        ),
        (
            FeedHealth(),
            FetchFailure.parse(),
            OCT26_0915,
            FeedHealth(FeedStatus.PARSE_FAILED, OCT26_0915, OCT26_0915),
        ),
        (
            FeedHealth(FeedStatus.PARSE_FAILED, OCT26_0915, OCT26_0915),
            FetchFailure.http_status(503),
            OCT26_0930,
            FeedHealth(FeedStatus.FETCH_FAILED, OCT26_0930, OCT26_0915),
        ),
    ],
    ids=[
        "first_failure_sets_failing_since",
        "later_failure_keeps_failing_since",
        "success_clears_failing_since",
        "parse_failure_on_a_new_feed",
        "fetch_failure_after_parse_failure_keeps_failing_since",
    ],
)
def test_r11_health_after_a_read(
    before: FeedHealth,
    result: ParsedFeed | FetchFailure,
    at: datetime,
    after: FeedHealth,
) -> None:
    feed = Feed(id=1, url=URL, health=before)

    assert feed.health_after(result, at) == after
