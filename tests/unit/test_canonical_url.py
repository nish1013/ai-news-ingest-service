from ingest.domain.article import CanonicalUrl


def test_s6_ac1_link_becomes_canonical_url() -> None:
    url = CanonicalUrl.from_link("https://Example.com/gpt-6/?utm_source=rss&id=7#top")

    assert url.value == "https://example.com/gpt-6?id=7"
