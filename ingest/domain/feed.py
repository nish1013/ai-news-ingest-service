"""Feed values: feed rules, a registered feed and the result of one read."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ingest.domain.errors import IngestError


class FeedRuleReason(StrEnum):
    """The feed rule a feed command broke."""

    URL_SCHEME = "url_scheme"
    URL_MISSING = "url_missing"
    NAME_MISSING = "name_missing"
    URL_TAKEN = "url_taken"
    HAS_ARTICLES = "has_articles"


class FeedRuleError(IngestError):
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
        raise NotImplementedError


@dataclass(frozen=True)
class FeedDetails:
    """The name and URL the owner gives a feed."""

    name: str
    url: FeedUrl

    @classmethod
    def create(cls, *, name: str, url: str) -> "FeedDetails":
        """Return the details, or raise FeedRuleError with the broken rule."""
        raise NotImplementedError


@dataclass(frozen=True)
class Feed:
    """A registered feed in a pass list."""

    id: int
    name: str
    url: str


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
