"""Article values: the canonical URL rule, a new article and its outcomes."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PREFIX = "utm_"


class ArticleRejectReason(StrEnum):
    """The link rule an item broke."""

    LINK_MISSING = "link_missing"
    LINK_NOT_ABSOLUTE = "link_not_absolute"


@dataclass(frozen=True)
class CanonicalUrl:
    """An item link in one form per page."""

    value: str

    @classmethod
    def from_link(cls, link: str) -> "CanonicalUrl":
        """Return the canonical form of an item link."""
        parts = urlsplit(link)
        query = [
            (name, value)
            for name, value in parse_qsl(parts.query, keep_blank_values=True)
            if not name.startswith(_TRACKING_PREFIX)
        ]
        return cls(
            urlunsplit(
                (
                    parts.scheme.lower(),
                    parts.netloc.lower(),
                    parts.path.rstrip("/"),
                    urlencode(query),
                    "",
                )
            )
        )


@dataclass(frozen=True)
class NewArticle:
    """An article the pass asks the store to keep."""

    feed_id: int
    canonical_url: CanonicalUrl
    title: str
    published_at: datetime | None


@dataclass(frozen=True)
class ArticleStored:
    """The store keeps a new article."""

    canonical_url: CanonicalUrl


@dataclass(frozen=True)
class DuplicateArticleSkipped:
    """The store has the canonical URL. The first copy stays as it is."""

    canonical_url: CanonicalUrl


@dataclass(frozen=True)
class ArticleRejected:
    """The item link broke a link rule. Nothing is stored."""

    link: str
    reason: ArticleRejectReason


ArticleOutcome = ArticleStored | DuplicateArticleSkipped | ArticleRejected
