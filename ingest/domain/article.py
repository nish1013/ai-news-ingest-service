"""Article values: the canonical URL rule, a new article and its outcomes."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from urllib.parse import unquote_plus, urlsplit, urlunsplit

ON_TIME_LIMIT = timedelta(minutes=30)

_LINK_SCHEMES = frozenset({"http", "https"})
_TRACKER_PREFIX = "utm_"
_TRACKERS = frozenset({"fbclid", "gclid", "mc_cid", "mc_eid"})


class ArticleRejectReason(StrEnum):
    """The link rule an item broke."""

    LINK_MISSING = "link_missing"
    LINK_NOT_ABSOLUTE = "link_not_absolute"


class ArticleRuleError(Exception):
    """An item link broke a link rule."""

    def __init__(self, reason: ArticleRejectReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


@dataclass(frozen=True)
class CanonicalUrl:
    """An item link in one form per page."""

    value: str

    @classmethod
    def from_link(cls, link: str) -> "CanonicalUrl":
        """Return the canonical form of an item link, or raise ArticleRuleError."""
        text = link.strip()
        if not text:
            raise ArticleRuleError(ArticleRejectReason.LINK_MISSING)
        try:
            parts = urlsplit(text)
            _ = parts.port  # raises ValueError on a bad port
            absolute = parts.scheme.lower() in _LINK_SCHEMES and bool(parts.hostname)
        except ValueError as err:
            raise ArticleRuleError(ArticleRejectReason.LINK_NOT_ABSOLUTE) from err
        if not absolute:
            raise ArticleRuleError(ArticleRejectReason.LINK_NOT_ABSOLUTE)
        query = "&".join(
            pair for pair in parts.query.split("&") if pair and not _is_tracker(pair)
        )
        return cls(
            urlunsplit(
                (
                    parts.scheme.lower(),
                    parts.netloc.lower(),
                    parts.path.rstrip("/"),
                    query,
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
    stored_at: datetime


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


def _is_tracker(pair: str) -> bool:
    name = unquote_plus(pair.partition("=")[0])
    return name.startswith(_TRACKER_PREFIX) or name in _TRACKERS
