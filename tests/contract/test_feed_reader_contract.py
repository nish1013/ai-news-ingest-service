from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import pytest
from ingest.adapters.feed_reader import HttpFeedReader

from ingest.application.ports import FeedReader
from ingest.domain.feed import FeedItem, ParsedFeed
from tests.fakes import StubFeedReader
from tests.feed_server import feed_server, rss

Publish = Callable[[list[FeedItem]], str]

THREE_ITEMS = [
    FeedItem(
        link="https://example.com/gpt-6",
        title="GPT-6 is out",
        published_at=datetime(2026, 10, 26, 8, 0, tzinfo=UTC),
    ),
    FeedItem(
        link="https://example.com/agents?id=2",
        title="Agents & tools",
        published_at=datetime(2026, 10, 26, 8, 30, tzinfo=UTC),
    ),
    FeedItem(link="https://example.com/no-date", title="No date", published_at=None),
]


@pytest.fixture(params=["stub", "http"])
def reader_and_publish(
    request: pytest.FixtureRequest,
) -> Iterator[tuple[FeedReader, Publish]]:
    if request.param == "stub":
        stub = StubFeedReader()

        def publish_stub(items: list[FeedItem]) -> str:
            url = "https://batch.test/feed"
            stub.results[url] = ParsedFeed(items=tuple(items))
            return url

        yield stub, publish_stub
    else:
        with feed_server() as server:

            def publish_http(items: list[FeedItem]) -> str:
                return server.serve("/the-batch/feed/", rss(items))

            yield HttpFeedReader(), publish_http


def test_s5_ac1_feed_with_three_rss_items_parses_to_three_items(
    reader_and_publish: tuple[FeedReader, Publish],
) -> None:
    reader, publish = reader_and_publish
    url = publish(THREE_ITEMS)

    result = reader.read(url)

    assert result == ParsedFeed(items=tuple(THREE_ITEMS))
