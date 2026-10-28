"""FeedReader adapter: httpx for the fetch, feedparser for the body."""

from ingest.domain.feed import FetchFailure, ParsedFeed


class HttpFeedReader:
    """Reads a feed over HTTP and parses RSS or Atom bytes."""

    def read(self, url: str) -> ParsedFeed | FetchFailure:
        """Return the parsed items, or the reason the read failed."""
        raise NotImplementedError
