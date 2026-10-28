"""The ingest pass: read each active feed and store its items."""

from dataclasses import dataclass

from ingest.application.ports import (
    ArticleStore,
    Clock,
    FeedCatalog,
    FeedReader,
    PassLock,
    RunLog,
)
from ingest.domain.feed import Feed
from ingest.domain.run import RunCounts


@dataclass(frozen=True)
class PassReport:
    """The pass list and the counts of one pass."""

    feeds: tuple[Feed, ...]
    counts: RunCounts


class IngestPass:
    """Runs one ingest pass under the pass lock."""

    def __init__(
        self,
        *,
        catalog: FeedCatalog,
        reader: FeedReader,
        store: ArticleStore,
        lock: PassLock,
        run_log: RunLog,
        clock: Clock,
    ) -> None:
        self._catalog = catalog
        self._reader = reader
        self._store = store
        self._lock = lock
        self._run_log = run_log
        self._clock = clock

    def run(self) -> PassReport:
        """Run one pass and write its run record."""
        raise NotImplementedError
