"""Feed commands of the owner: register and edit a feed."""

from dataclasses import dataclass

from ingest.application.ports import FeedCatalog
from ingest.domain.feed import FeedDetails, FeedRuleError, FeedRuleReason


@dataclass(frozen=True)
class FeedRegistered:
    """A new feed is in the catalog and active."""

    feed_id: int


@dataclass(frozen=True)
class FeedEdited:
    """A feed has a new name or URL."""

    feed_id: int


@dataclass(frozen=True)
class FeedRejected:
    """A register or edit broke a feed rule. The catalog did not change."""

    reason: FeedRuleReason


class FeedCommands:
    """Changes the feed catalog under the feed rules."""

    def __init__(self, catalog: FeedCatalog) -> None:
        self._catalog = catalog

    def register(self, *, name: str, url: str) -> FeedRegistered | FeedRejected:
        """Add a feed. It starts active."""
        try:
            feed_id = self._catalog.add(FeedDetails.create(name=name, url=url))
        except FeedRuleError as err:
            return FeedRejected(err.reason)
        return FeedRegistered(feed_id)

    def edit(self, feed_id: int, *, name: str, url: str) -> FeedEdited | FeedRejected:
        """Give a feed a new name and URL."""
        try:
            self._catalog.update(feed_id, FeedDetails.create(name=name, url=url))
        except FeedRuleError as err:
            return FeedRejected(err.reason)
        return FeedEdited(feed_id)
