from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import pytest

from ingest.adapters.feed_reader import HttpFeedReader
from ingest.application.ports import FeedReader
from ingest.domain.feed import FeedItem, FetchFailure, ParsedFeed
from tests.fakes import StubFeedReader
from tests.feed_server import (
    FeedServer,
    Reply,
    closed_port_url,
    empty_atom,
    feed_server,
    html_page,
    rss,
)

DEADLINE_SECONDS = 0.3
MAX_BODY_BYTES = 1000

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


class Publisher(Protocol):
    def rss(self, items: list[FeedItem]) -> str: ...
    def empty_atom(self) -> str: ...
    def html(self) -> str: ...
    def status(self, code: int) -> str: ...
    def silent(self) -> str: ...
    def drip(self) -> str: ...
    def large(self) -> str: ...
    def refused(self) -> str: ...


@dataclass
class StubPublisher:
    stub: StubFeedReader

    def rss(self, items: list[FeedItem]) -> str:
        return self._set("rss", ParsedFeed(items=tuple(items)))

    def empty_atom(self) -> str:
        return self._set("atom", ParsedFeed(items=()))

    def html(self) -> str:
        return self._set("html", FetchFailure.parse())

    def status(self, code: int) -> str:
        return self._set(f"status-{code}", FetchFailure.http_status(code))

    def silent(self) -> str:
        return self._set("silent", FetchFailure.timeout())

    def drip(self) -> str:
        return self._set("drip", FetchFailure.timeout())

    def large(self) -> str:
        return self._set("large", FetchFailure.too_large())

    def refused(self) -> str:
        return self._set("refused", FetchFailure.connection())

    def _set(self, name: str, result: ParsedFeed | FetchFailure) -> str:
        url = f"https://openai.test/{name}"
        self.stub.results[url] = result
        return url


@dataclass
class HttpPublisher:
    server: FeedServer

    def rss(self, items: list[FeedItem]) -> str:
        return self.server.serve("/the-batch/feed/", rss(items))

    def empty_atom(self) -> str:
        return self.server.serve("/atom.xml", empty_atom())

    def html(self) -> str:
        return self.server.serve("/blog", html_page())

    def status(self, code: int) -> str:
        return self.server.reply("/status", Reply(body=b"down", status=code))

    def silent(self) -> str:
        return self.server.reply("/silent", Reply(stall=True))

    def drip(self) -> str:
        body = rss(THREE_ITEMS)
        return self.server.reply("/drip", Reply(body=body, drip_seconds=0.02))

    def large(self) -> str:
        body = b"x" * (MAX_BODY_BYTES * 3)
        return self.server.reply("/large", Reply(body=body, send_length=False))

    def refused(self) -> str:
        return closed_port_url()


@pytest.fixture(params=["stub", "http"])
def reader_and_publisher(
    request: pytest.FixtureRequest,
) -> Iterator[tuple[FeedReader, Publisher]]:
    if request.param == "stub":
        stub = StubFeedReader()
        yield stub, StubPublisher(stub)
    else:
        with feed_server() as server:
            reader = HttpFeedReader(
                deadline_seconds=DEADLINE_SECONDS, max_body_bytes=MAX_BODY_BYTES
            )
            yield reader, HttpPublisher(server)


def test_s5_ac1_feed_with_three_rss_items_parses_to_three_items(
    reader_and_publisher: tuple[FeedReader, Publisher],
) -> None:
    reader, publish = reader_and_publisher

    result = reader.read(publish.rss(THREE_ITEMS))

    assert result == ParsedFeed(items=tuple(THREE_ITEMS))


def test_s5_ac2_feed_with_no_response_fails_as_timeout(
    reader_and_publisher: tuple[FeedReader, Publisher],
) -> None:
    reader, publish = reader_and_publisher

    assert reader.read(publish.silent()) == FetchFailure.timeout()


def test_s5_ac3_feed_with_503_fails_as_http_503(
    reader_and_publisher: tuple[FeedReader, Publisher],
) -> None:
    reader, publish = reader_and_publisher

    result = reader.read(publish.status(503))

    assert result == FetchFailure.http_status(503)
    assert result.reason == "http_503"  # type: ignore[union-attr]


def test_s5_ac4_html_page_fails_as_parse(
    reader_and_publisher: tuple[FeedReader, Publisher],
) -> None:
    reader, publish = reader_and_publisher

    assert reader.read(publish.html()) == FetchFailure.parse()


def test_s5_ac5_atom_feed_with_no_entries_parses_to_no_items(
    reader_and_publisher: tuple[FeedReader, Publisher],
) -> None:
    reader, publish = reader_and_publisher

    assert reader.read(publish.empty_atom()) == ParsedFeed(items=())


def test_s5_ac10_slow_drip_fails_as_timeout_on_the_total_deadline(
    reader_and_publisher: tuple[FeedReader, Publisher],
) -> None:
    reader, publish = reader_and_publisher

    assert reader.read(publish.drip()) == FetchFailure.timeout()


def test_s5_ac11_body_over_the_cap_fails_as_too_large(
    reader_and_publisher: tuple[FeedReader, Publisher],
) -> None:
    reader, publish = reader_and_publisher

    assert reader.read(publish.large()) == FetchFailure.too_large()


def test_r4_refused_connection_fails_as_connection(
    reader_and_publisher: tuple[FeedReader, Publisher],
) -> None:
    reader, publish = reader_and_publisher

    assert reader.read(publish.refused()) == FetchFailure.connection()


def test_s5_ac10_redirect_hops_past_the_total_deadline_fail_as_timeout() -> None:
    hop_delay = DEADLINE_SECONDS * 2 / 3
    with feed_server() as server:
        final = server.reply("/final", Reply(header_delay_seconds=hop_delay))
        first = server.reply(
            "/first",
            Reply(status=302, location=final, header_delay_seconds=hop_delay),
        )
        reader = HttpFeedReader(deadline_seconds=DEADLINE_SECONDS)

        assert reader.read(first) == FetchFailure.timeout()


@pytest.mark.parametrize(
    "url", ["http://ex.com:abc/", "http://ex.com/\x00", "http://xn--a.com/"]
)
def test_r9_url_the_client_rejects_before_the_request_fails_as_connection(
    url: str,
) -> None:
    reader = HttpFeedReader(deadline_seconds=DEADLINE_SECONDS)

    assert reader.read(url) == FetchFailure.connection()


def test_d20_reader_defaults_are_a_10_s_deadline_and_a_5_mb_cap() -> None:
    reader = HttpFeedReader()

    assert (reader.deadline_seconds, reader.max_body_bytes) == (10.0, 5 * 1024 * 1024)
