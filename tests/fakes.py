from dataclasses import dataclass, field
from datetime import UTC, datetime

from ingest.domain.article import NewArticle
from ingest.domain.feed import Feed, FeedItem, FetchFailure, ParsedFeed
from ingest.domain.run import RunCounts

PUBLISHED = datetime(2026, 10, 26, 8, 50, tzinfo=UTC)


def feed_items(feed_id: int, count: int) -> ParsedFeed:
    return ParsedFeed(
        items=tuple(
            FeedItem(
                link=f"https://example.com/{feed_id}/{n}",
                title=f"Item {n}",
                published_at=PUBLISHED,
            )
            for n in range(count)
        )
    )


@dataclass
class InMemoryFeedCatalog:
    feeds: list[tuple[Feed, bool]] = field(default_factory=list)

    def add(self, feed: Feed, *, active: bool = True) -> None:
        self.feeds.append((feed, active))

    def active_feeds(self) -> list[Feed]:
        return [feed for feed, active in self.feeds if active]


@dataclass
class StubFeedReader:
    results: dict[str, ParsedFeed | FetchFailure] = field(default_factory=dict)
    read_urls: list[str] = field(default_factory=list)

    def read(self, url: str) -> ParsedFeed | FetchFailure:
        self.read_urls.append(url)
        return self.results[url]


@dataclass
class InMemoryArticleStore:
    articles: list[NewArticle] = field(default_factory=list)

    def add(self, article: NewArticle) -> bool:
        if any(a.canonical_url == article.canonical_url for a in self.articles):
            return False
        self.articles.append(article)
        return True


@dataclass
class FakePassLock:
    held: bool = False
    acquired: int = 0

    def acquire(self) -> None:
        self.held = True
        self.acquired += 1

    def release(self) -> None:
        self.held = False


@dataclass
class InMemoryRunLog:
    started: list[datetime] = field(default_factory=list)
    finished: dict[int, RunCounts] = field(default_factory=dict)

    def start(self, started_at: datetime) -> int:
        self.started.append(started_at)
        return len(self.started)

    def finish(self, run_id: int, counts: RunCounts, finished_at: datetime) -> None:
        self.finished[run_id] = counts


@dataclass
class FixedClock:
    at: datetime = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.at
