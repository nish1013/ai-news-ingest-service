"""Article values: the canonical URL rule and a new article."""

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PREFIX = "utm_"


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
