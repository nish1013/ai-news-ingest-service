"""Feed commands of the owner: register, edit, turn on or off, delete."""

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


@dataclass(frozen=True)
class FeedDeactivated:
    """The next pass does not read the feed."""

    feed_id: int


@dataclass(frozen=True)
class FeedReactivated:
    """The next pass reads the feed."""

    feed_id: int


@dataclass(frozen=True)
class FeedDeleted:
    """The feed is gone from the catalog."""

    feed_id: int


@dataclass(frozen=True)
class FeedDeleteRefused:
    """The feed stays, with its articles."""

    feed_id: int
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

    def set_active(
        self, feed_id: int, *, active: bool
    ) -> FeedDeactivated | FeedReactivated:
        """Turn a feed on or off for the next pass."""
        self._catalog.set_active(feed_id, active=active)
        if active:
            return FeedReactivated(feed_id)
        return FeedDeactivated(feed_id)

    def delete(self, feed_id: int) -> FeedDeleted | FeedDeleteRefused:
        """Remove a feed that has no stored articles."""
        try:
            self._catalog.delete(feed_id)
        except FeedRuleError as err:
            return FeedDeleteRefused(feed_id, err.reason)
        return FeedDeleted(feed_id)
