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
        response = httpx.get(url, timeout=DEADLINE_SECONDS, follow_redirects=True)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
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
