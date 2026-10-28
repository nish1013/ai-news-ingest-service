import pytest

from ingest.domain.feed import FeedDetails, FeedRuleError, FeedRuleReason, FeedUrl


@pytest.mark.parametrize(
    "text",
    [
        "https://www.deeplearning.ai/the-batch/feed/",
        "http://example.com/rss.xml",
        "HTTPS://Example.com/feed",
    ],
)
def test_r1_absolute_http_or_https_url_is_a_feed_url(text: str) -> None:
    assert FeedUrl.from_text(text).value == text


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("ftp://x.org/feed", FeedRuleReason.URL_SCHEME),
        ("openai.com/blog", FeedRuleReason.URL_SCHEME),
        ("/blog/rss.xml", FeedRuleReason.URL_SCHEME),
        ("https://", FeedRuleReason.URL_SCHEME),
        ("javascript:alert(1)", FeedRuleReason.URL_SCHEME),
        ("http://[::1/feed", FeedRuleReason.URL_SCHEME),
        ("", FeedRuleReason.URL_MISSING),
        ("   ", FeedRuleReason.URL_MISSING),
    ],
)
def test_r1_other_text_is_refused_with_its_reason(
    text: str, reason: FeedRuleReason
) -> None:
    with pytest.raises(FeedRuleError) as refused:
        FeedUrl.from_text(text)

    assert refused.value.reason == reason


def test_r1_url_keeps_its_text_after_the_outer_spaces() -> None:
    assert FeedUrl.from_text(" https://x.org/feed ").value == "https://x.org/feed"


@pytest.mark.parametrize("name", ["", "  "])
def test_blank_feed_name_is_refused(name: str) -> None:
    with pytest.raises(FeedRuleError) as refused:
        FeedDetails.create(name=name, url="https://x.org/feed")

    assert refused.value.reason == FeedRuleReason.NAME_MISSING


def test_feed_details_hold_the_name_and_the_feed_url() -> None:
    details = FeedDetails.create(name=" The Batch ", url="https://x.org/feed")

    assert (details.name, details.url) == (
        "The Batch",
        FeedUrl("https://x.org/feed"),
    )
