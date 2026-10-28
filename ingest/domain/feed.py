"""Feed values: a registered feed and the result of one read."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Feed:
    """A registered feed in a pass list."""

    id: int
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
