# Event Storming: AI news ingest worker

The ingest pass has one invariant: one article per canonical URL. Every other "no" is a per-request check.

Source of each event: U user, B business, F failure, O outside.

## Timeline

```
Owner --admin--> FeedRegistered ─┬─> FeedEdited ─> FeedDeactivated ─> FeedReactivated
                 └> FeedRejected  ⚡H1 ⚡H2

cron tick (15 min) ─> IngestPassStarted ──────────────────────────────┐
                   └> IngestPassSkipped (lock taken)                   │
                                                                       v
  per active feed:  FeedFetched ─> FeedParsed ─> per item ─┬─> ArticleStored
                    └> FeedFetchFailed  └> FeedParseFailed  ├─> DuplicateArticleSkipped  ⚡H6
                                         ⚡H3 ⚡H4           └─> ArticleRejected
                                                                       │
  IngestPassCompleted (run record: feeds ok, feeds failed, articles new)
  └> IngestPassCrashed  ⚡H7

outside the system:  TrialPeriodEnded ─> MvpPromoted | FeedListRevised | MvpDropped
```

| # | Event | Source | Meaning |
|---|---|---|---|
| E1 | FeedRegistered | U B O | The owner adds a feed with a name and a URL. The feed is active. |
| E2 | FeedRejected | U | Admin refuses a feed with a missing or invalid URL. |
| E3 | FeedEdited | U | The owner changes the name or the URL of a feed. |
| E4 | FeedDeactivated | U B O F | The owner clears the active flag. Later passes skip the feed. |
| E5 | FeedReactivated | U B | The owner sets the active flag again. |
| E6 | IngestPassStarted | U B O | A cron tick starts a pass. The pass takes the advisory lock. |
| E7 | IngestPassSkipped | U B O F | A tick finds the lock taken. The tick exits with no work. |
| E8 | FeedFetched | U B O | A feed answers with HTTP 2xx within 10 s. |
| E9 | FeedFetchFailed | U B O F | A feed times out, returns an HTTP error, or the connection fails. The reason is kept. |
| E10 | FeedParsed | B O | The body becomes a list of items in one article shape. Zero items is valid. |
| E11 | FeedParseFailed | U B O F | The body is not valid RSS 2.0 or Atom. |
| E12 | ArticleRejected | F | An item has no link, or its link is not an absolute http(s) URL. |
| E13 | ArticleStored | U B O F | The first item with a new canonical URL enters the store. |
| E14 | DuplicateArticleSkipped | U B O F | The canonical URL is already stored. The first copy stays. |
| E15 | IngestPassCompleted | U B O F | The pass writes its run record and releases the lock. |
| E16 | IngestPassCrashed | U F | The process dies before the run record is complete. |
| E18 | FeedDeleted | U F | The owner deletes a feed with no stored articles. |
| E19 | FeedDeleteRefused | F | Admin refuses to delete a feed with stored articles (D15). |
| E17 | TrialPeriodEnded | U B O | 14 days of passes end. The owner reads the metric. Outside the system. |

Merged as one event: `FeedFetchTimedOut`, `FeedFetchRejected` into E9 with a reason. `IngestPassSkippedAsBusy`, `IngestPassOverran` into E7.

Not events: `ArticleUrlCanonicalised` is a value object step. `ArticleStoredLate` and `FreshnessTargetMet` are derived on read from `stored_at - published_at`. `LockReleasedOnCrash` is Postgres behaviour.

## Hot spots

| ⚡ | At | Doubt | Sort |
|---|---|---|---|
| H1 | E1 | Can two feeds have the same URL? | product |
| H2 | E3, E4 | The owner deletes a feed that has stored articles. What happens to the articles? | product |
| H3 | E10 | An item has no published date, or an unreadable one. Store it or reject it? The metric needs the date. | product |
| H4 | E10 | An item gives a published date after the fetch time. Keep it as given? | product |
| H5 | E9 | A feed fails on many ticks in a row. Where does the owner see it? | product |
| H6 | E14 | Two items with one canonical URL in the same pass, or in one feed. Which one wins? | tech |
| H7 | E16 | A crash leaves stored articles and an open run record. How does the record show it? | tech |
| H8 | E6 | Worst case pass time: 20 feeds x 10 s = 200 s, under 15 min. A slow body read can pass the 10 s connect limit. | tech |
| H9 | E13 | The canonical rule removes `utm_*` only. Other trackers (`ref`, `fbclid`) stay. | product |

## "No" events and the rule that says no

| Event | Rule | Candidate invariant |
|---|---|---|
| E2 FeedRejected | A feed URL is an absolute http(s) URL. | No. A check on one request. |
| E19 FeedDeleteRefused | A feed with stored articles stays. | Yes. A protected foreign key guards it. |
| E7 IngestPassSkipped | One pass runs at a time. | Yes. The advisory lock guards it. |
| E9 FeedFetchFailed | A feed answers with 2xx within 10 s. | No. A check on one fetch. |
| E11 FeedParseFailed | The body is RSS 2.0 or Atom. | No. A check on one body. |
| E12 ArticleRejected | An item link is an absolute http(s) URL. | No. A check on one item. |
| E14 DuplicateArticleSkipped | One article per canonical URL. | Yes. A unique key guards it. |

## Process

Each event has one cause: a role sent a command, time passed, or another event happened.

| Event | Trigger | Command | Role | Policy | View |
|---|---|---|---|---|---|
| E1 FeedRegistered, E2 FeedRejected | role | RegisterFeed | Owner | | Admin feed list |
| E3 FeedEdited, E2 FeedRejected | role | EditFeed | Owner | | Admin feed form |
| E4 FeedDeactivated, E5 FeedReactivated | role | SetFeedActive | Owner | | Admin feed list with last status (H5) |
| E18 FeedDeleted, E19 FeedDeleteRefused | role | DeleteFeed | Owner | | Admin feed list |
| E6 IngestPassStarted, E7 IngestPassSkipped | time | StartIngestPass | Cron | P1 whenever 15 min pass, start a pass | |
| E8 FeedFetched, E9 FeedFetchFailed, E10 FeedParsed, E11 FeedParseFailed | event | ReadFeed | Ingest pass | P2 whenever a pass starts, read each active feed in turn | |
| E12 ArticleRejected, E13 ArticleStored, E14 DuplicateArticleSkipped | event | IngestArticle | Ingest pass | P3 whenever a feed is parsed, ingest each item | |
| E15 IngestPassCompleted | event | CompleteIngestPass | Ingest pass | P4 whenever every active feed is read, complete the pass | Run records in admin |
| E16 IngestPassCrashed | outside | none | Process | | Open run record (H7) |
| E17 TrialPeriodEnded | outside | none | Owner | | Metric query |

E16 and E17 have no command. E16 is a process death. E17 is an owner decision outside the system.

## Views

| View | Role | Shows |
|---|---|---|
| Admin feed list | Owner | Name, URL, active flag, last read status, last read time. |
| Admin article list | Owner | Title, source feed, published, stored, canonical URL. Newest first. |
| Admin run records | Owner | Started, finished, feeds ok, feeds failed, articles new. |
| Metric query | Owner | Share of articles with `stored_at - published_at` under 30 min. Duplicate count. |
