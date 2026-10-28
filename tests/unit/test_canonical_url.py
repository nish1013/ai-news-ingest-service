import pytest

from ingest.domain.article import ArticleRejectReason, ArticleRuleError, CanonicalUrl


def test_s6_ac1_link_becomes_canonical_url() -> None:
    url = CanonicalUrl.from_link("https://Example.com/gpt-6/?utm_source=rss&id=7#top")

    assert url.value == "https://example.com/gpt-6?id=7"


def test_s6_ac8_parameter_order_stays() -> None:
    url = CanonicalUrl.from_link("https://example.com/a?b=2&a=1")

    assert url.value == "https://example.com/a?b=2&a=1"


def test_s6_ac11_the_five_trackers_go_and_other_parameters_stay() -> None:
    url = CanonicalUrl.from_link(
        "https://example.com/a?fbclid=x&gclid=y&mc_cid=z&ref=hn&mc_eid=w&utm_medium=rss"
    )

    assert url.value == "https://example.com/a?ref=hn"


@pytest.mark.parametrize(
    ("link", "reason"),
    [
        ("", ArticleRejectReason.LINK_MISSING),
        ("   ", ArticleRejectReason.LINK_MISSING),
        ("/news/42", ArticleRejectReason.LINK_NOT_ABSOLUTE),
        ("example.com/news/42", ArticleRejectReason.LINK_NOT_ABSOLUTE),
        ("ftp://example.com/a", ArticleRejectReason.LINK_NOT_ABSOLUTE),
        ("mailto:news@example.com", ArticleRejectReason.LINK_NOT_ABSOLUTE),
        ("https:///a", ArticleRejectReason.LINK_NOT_ABSOLUTE),
        ("http://[::1/a", ArticleRejectReason.LINK_NOT_ABSOLUTE),
    ],
)
def test_r7_link_is_an_absolute_http_or_https_url(
    link: str, reason: ArticleRejectReason
) -> None:
    with pytest.raises(ArticleRuleError) as err:
        CanonicalUrl.from_link(link)

    assert err.value.reason == reason


@pytest.mark.parametrize(
    "link",
    [
        "https://x.com:abc/a",
        "http://x.com:99999/a",
        "http://x.com:-1/a",
    ],
)
def test_r7_link_with_a_bad_port_is_not_absolute(link: str) -> None:
    with pytest.raises(ArticleRuleError) as err:
        CanonicalUrl.from_link(link)

    assert err.value.reason == ArticleRejectReason.LINK_NOT_ABSOLUTE


@pytest.mark.parametrize(
    ("link", "canonical"),
    [
        ("https://User:Pass@X.com/a", "https://User:Pass@x.com/a"),
        ("https://X.com:8443/a", "https://x.com:8443/a"),
        ("https://Me@Example.COM:80/a", "https://Me@example.com:80/a"),
        ("http://[ABCD::1]:8080/a", "http://[abcd::1]:8080/a"),
    ],
)
def test_r8_only_the_host_is_lower_cased(link: str, canonical: str) -> None:
    assert CanonicalUrl.from_link(link).value == canonical


def test_r8_query_text_stays_as_the_feed_gave_it() -> None:
    url = CanonicalUrl.from_link("HTTP://Example.com/a/?q=a%20b&flag&utm_id=1")

    assert url.value == "http://example.com/a?q=a%20b&flag"
