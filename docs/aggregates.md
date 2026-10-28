# Aggregates, contexts and checks

One aggregate (Feed), two set guards (unique article URL, one pass lock), one context (Ingest).

## Rule per command

| Command | Rule | Timing | Reads | Aggregate | Guard |
|---|---|---|---|---|---|
| RegisterFeed | R1 URL is absolute http(s). R9 URL is unique. | immediate | All feed URLs | none, a set rule | Unique key on `feed.url`. `FeedUrl` value object. |
| EditFeed | R1, R9 | immediate | All feed URLs | none, a set rule | Unique key on `feed.url` |
| SetFeedActive | none | immediate | One feed | Feed(feed_id) | none |
| DeleteFeed | R10 a feed with articles stays | immediate | Articles of one feed | Feed(feed_id) | `PROTECT` foreign key from `article.feed_id` |
| StartIngestPass | R3 one pass at a time | immediate | The pass lock | none, a set rule | Postgres advisory lock, one fixed key |
| ReadFeed | R4 2xx in 10 s. R5 RSS or Atom. R11 failing_since. | immediate | One feed health | Feed(feed_id) | One row update |
| IngestArticle | R6 one article per canonical URL. R7 absolute link. | immediate | All canonical URLs | none, a set rule | Unique key on `article.canonical_url`. `CanonicalUrl` value object. |
| CompleteIngestPass | none | none | One run record | none, plain data | none |

## Rules two requests can break

| ⚠ | Rule | Two requests | Guard | Test |
|---|---|---|---|---|
| ⚠ | R6 one article per canonical URL | Two writers insert `https://example.com/a`. 1 + 1 = 2 rows > 1. | Unique key | Two connections insert at once. Without the key, the test sees 2 rows. |
| ⚠ | R3 one pass at a time | Two ticks at 09:15:00. 1 + 1 = 2 passes > 1. | Advisory lock | Two connections take the lock. Without the lock, both start. |
| ⚠ | R10 feed with articles stays | Ana deletes "Batch" while a pass stores its first article. | `PROTECT` foreign key | Delete in one connection, insert in the other. One fails. |

## Values

| Value object | Rule it checks when created |
|---|---|
| `FeedUrl` | Absolute http or https URL. Not empty. |
| `CanonicalUrl` | Lower-case scheme and host. No fragment. No tracking parameter. No trailing slash. Other parameters keep their order. |
| `FetchFailure` | A reason: `timeout`, `http_<code>`, `connection`, `too_large`, `parse`. |

## Status

| Status | Stored or derived | Why |
|---|---|---|
| Feed `last_status`, `failing_since` | Stored | The pass decides it. No other source holds it. |
| Run record "unfinished" | Derived: `finished_at` empty | A crash cannot write a status. |
| Article "on time" | Derived: `stored_at - published_at` under 30 min | A query computes it. |

## Context

One context: Ingest. One owner (the digest owner), one language (feed, article, pass).

```
           ┌──────────────── Ingest context (one Django app: ingest) ────────────────┐
 Owner ──> │ admin adapter ─┐                                                          │
 cron  ──> │ command adapter ┴─> application: IngestPass, FeedCommands                 │
           │                       │ uses ports                                        │
           │                  domain: Feed, CanonicalUrl, FeedUrl, FetchFailure, rules │
           │ ports: FeedCatalog · ArticleStore · PassLock · RunLog · FeedReader · Clock│
           │ adapters: Django ORM · Postgres lock · httpx + feedparser · system clock  │
           └───────────────────────────────────────────┬─────────────────────────────┘
                                                       v
                                  outside: feed publishers (HTTP), behind FeedReader
```

The FeedReader adapter turns HTTP and `feedparser` results into `FetchFailure` reasons. No HTTP status or `feedparser` type enters the domain.

## Policies

| Policy | Strategy | Why |
|---|---|---|
| P1 each 15 min, start a pass | Cron, outside the system | D1 |
| P2 pass started, read each feed | In-process call, in order, in the same run | One process, one database. No lag is wanted. |
| P3 feed parsed, ingest each item | In-process call, one transaction per feed | A crash loses at most one feed batch. The next tick repeats it. |
| P4 all feeds read, complete the pass | In-process call | The run record is the last step. |

No outbox and no broker. A crash between P2 and P4 is safe: the unique key makes the next tick idempotent.

## Checks

| Check | Result |
|---|---|
| Every event has a command or a policy | Pass. E16 crash and E17 trial end have none, with a reason in `eventstorm.md`. |
| Every command has a role or a policy | Pass |
| Every word comes from the timeline | Pass |
| One command changes one aggregate or one set | Pass. ReadFeed changes feed health. IngestArticle inserts articles. |
| Each fact lives in one place | Pass. Feed health lives on the feed row only. |
| Each policy names its strategy | Pass |
| Each arrow between contexts is ask | Pass. One context. Publishers are behind a port. |
