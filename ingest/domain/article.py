"""Article values: the canonical URL rule and a new article."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CanonicalUrl:
    """An item link in one form per page."""

    value: str

    @classmethod
    def from_link(cls, link: str) -> "CanonicalUrl":
        """Return the canonical form of an item link."""
        raise NotImplementedError


@dataclass(frozen=True)
class NewArticle:
    """An article the pass asks the store to keep."""

    feed_id: int
    canonical_url: CanonicalUrl
    title: str
    published_at: datetime | None
