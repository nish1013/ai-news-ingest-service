"""FeedReader adapter: httpx for the fetch, feedparser for the body."""

import time
from collections.abc import Mapping
from datetime import UTC, datetime

import feedparser
import httpx

from ingest.domain.feed import FeedItem, FetchFailure, ParsedFeed

DEADLINE_SECONDS = 10.0
MAX_BODY_BYTES = 5 * 1024 * 1024


class HttpFeedReader:
    """Reads a feed over HTTP and parses RSS or Atom bytes."""

    def __init__(
        self,
        *,
        deadline_seconds: float = DEADLINE_SECONDS,
        max_body_bytes: int = MAX_BODY_BYTES,
    ) -> None:
        self.deadline_seconds = deadline_seconds
        self.max_body_bytes = max_body_bytes

    def read(self, url: str) -> ParsedFeed | FetchFailure:
        """Return the parsed items, or the reason the read failed."""
        try:
            body = self._fetch(url)
        except httpx.TimeoutException:
            return FetchFailure.timeout()
        except (httpx.HTTPError, httpx.InvalidURL, UnicodeError):
            return FetchFailure.connection()
        if isinstance(body, FetchFailure):
            return body
        return _parse(body)

    def _fetch(self, url: str) -> bytes | FetchFailure:
        started = time.monotonic()
        with httpx.stream(
            "GET", url, timeout=self.deadline_seconds, follow_redirects=True
        ) as response:
            if not response.is_success:
                return FetchFailure.http_status(response.status_code)
            body = bytearray()
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > self.max_body_bytes:
                    return FetchFailure.too_large()
                if time.monotonic() - started > self.deadline_seconds:
                    return FetchFailure.timeout()
        return bytes(body)


def _parse(body: bytes) -> ParsedFeed | FetchFailure:
    parsed = feedparser.parse(body)
    if not parsed.get("version"):
        return FetchFailure.parse()
    return ParsedFeed(items=tuple(_item(entry) for entry in parsed.entries))


def _item(entry: Mapping[str, object]) -> FeedItem:
    return FeedItem(
        link=str(entry.get("link", "")),
        title=str(entry.get("title", "")),
        published_at=_published_at(entry.get("published_parsed")),
    )


def _published_at(parsed: object) -> datetime | None:
    if not isinstance(parsed, time.struct_time):
        return None
    return datetime(*parsed[:6], tzinfo=UTC)
