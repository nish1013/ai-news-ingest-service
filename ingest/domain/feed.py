"""Feed values: feed rules, a registered feed and the result of one read."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from urllib.parse import urlsplit

_FEED_SCHEMES = frozenset({"http", "https"})


class FeedRuleReason(StrEnum):
    """The feed rule a feed command broke."""

    URL_SCHEME = "url_scheme"
    URL_MISSING = "url_missing"
    NAME_MISSING = "name_missing"
    URL_TAKEN = "url_taken"
    HAS_ARTICLES = "has_articles"


class FeedRuleError(Exception):
    """A feed command broke a feed rule."""

    def __init__(self, reason: FeedRuleReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


@dataclass(frozen=True)
class FeedUrl:
    """A feed URL: an absolute http or https URL (R1)."""

    value: str

    @classmethod
    def from_text(cls, text: str) -> "FeedUrl":
        """Return the feed URL, or raise FeedRuleError with the broken rule."""
        value = text.strip()
        if not value:
            raise FeedRuleError(FeedRuleReason.URL_MISSING)
        try:
            parts = urlsplit(value)
        except ValueError as err:
            raise FeedRuleError(FeedRuleReason.URL_SCHEME) from err
        if parts.scheme.lower() not in _FEED_SCHEMES or not parts.hostname:
            raise FeedRuleError(FeedRuleReason.URL_SCHEME)
        return cls(value)


@dataclass(frozen=True)
class FeedDetails:
    """The name and URL the owner gives a feed."""

    name: str
    url: FeedUrl

    @classmethod
    def create(cls, *, name: str, url: str) -> "FeedDetails":
        """Return the details, or raise FeedRuleError with the broken rule."""
        clean_name = name.strip()
        if not clean_name:
            raise FeedRuleError(FeedRuleReason.NAME_MISSING)
        return cls(name=clean_name, url=FeedUrl.from_text(url))


class FeedStatus(StrEnum):
    """The result of the last read of a feed."""

    OK = "ok"
    FETCH_FAILED = "fetch_failed"
    PARSE_FAILED = "parse_failed"


@dataclass(frozen=True)
class FeedHealth:
    """The last read of a feed and the start of its current failure run (R11)."""

    last_status: FeedStatus | None = None
    last_read_at: datetime | None = None
    failing_since: datetime | None = None


@dataclass(frozen=True)
class Feed:
    """A registered feed in a pass list."""

    id: int
    url: str
    health: FeedHealth = FeedHealth()

    def health_after(
        self, result: "ParsedFeed | FetchFailure", at: datetime
    ) -> FeedHealth:
        """Return the feed health after a read at the given time."""
        raise NotImplementedError


@dataclass(frozen=True)
class FeedItem:
    """One item of a parsed feed, in one article shape."""

    link: str
    title: str
    published_at: datetime | None


@dataclass(frozen=True)
class ParsedFeed:
    """A feed body read as a list of items. Zero items is valid."""

    items: tuple[FeedItem, ...]


@dataclass(frozen=True)
class FetchFailure:
    """A feed read that gave no items, with its reason."""

    reason: str

    @classmethod
    def timeout(cls) -> "FetchFailure":
        """The feed missed the read deadline."""
        return cls("timeout")

    @classmethod
    def http_status(cls, code: int) -> "FetchFailure":
        """The feed answered with a status other than 2xx."""
        return cls(f"http_{code}")

    @classmethod
    def connection(cls) -> "FetchFailure":
        """The connection to the feed failed."""
        return cls("connection")

    @classmethod
    def too_large(cls) -> "FetchFailure":
        """The feed body is over the size cap."""
        return cls("too_large")

    @classmethod
    def parse(cls) -> "FetchFailure":
        """The body is not RSS or Atom."""
        return cls("parse")
