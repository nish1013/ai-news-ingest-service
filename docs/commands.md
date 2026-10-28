# Commands

Eight commands. Only IngestArticle can break an invariant: one article per canonical URL.

Feed values in the examples: "The Batch" `https://www.deeplearning.ai/the-batch/feed/`, "OpenAI blog" `https://openai.com/blog/rss.xml`.

### S1. RegisterFeed: As the owner I want to add a feed so that the next pass reads it

Rules        R1 a feed URL is an absolute http or https URL
             R2 a new feed is active
             R9 a feed URL is unique, compared exactly

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | No feeds | Ana registers "The Batch" with its URL | FeedRegistered, active = yes |
| AC2 | No feeds | Ana registers "Bad" with URL `ftp://x.org/feed` | FeedRejected(url_scheme) |
| AC3 | No feeds | Ana registers "Empty" with URL `""` | FeedRejected(url_missing) |
| AC4 | No feeds | Ana registers "Name pad" with name `"  "` | FeedRejected(name_missing) |
| AC5 | "The Batch" with URL `https://www.deeplearning.ai/the-batch/feed/` | Ana registers "Batch" with the same URL | FeedRejected(url_taken) |

Questions    Q1 (H1) can two feeds have the same URL?

### S2. EditFeed: As the owner I want to fix a feed name or URL so that a broken feed works again

Rules        R1 a feed URL is an absolute http or https URL
             R9 a feed URL is unique, compared exactly

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | "OpenAI blog" with URL `https://openai.com/rss` | Ana sets URL `https://openai.com/blog/rss.xml` | FeedEdited |
| AC2 | "OpenAI blog" | Ana sets URL `openai.com/blog` | FeedRejected(url_scheme) |
| AC3 | "OpenAI blog" with 12 stored articles | Ana changes the URL | FeedEdited. The 12 articles keep their link to the feed. |
| AC4 | "The Batch" and "OpenAI blog" | Ana sets the "OpenAI blog" URL to the "The Batch" URL | FeedRejected(url_taken) |

Questions    Q2 (H2) moved to S8

### S3. SetFeedActive: As the owner I want to turn a feed off and on so that a broken feed stops failing passes

Rules        none. Any feed can be turned off or on.

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | "OpenAI blog" active | Ana sets active = no | FeedDeactivated. The next pass does not read it. |
| AC2 | "OpenAI blog" inactive | Ana sets active = yes | FeedReactivated. The next pass reads it. |
| AC3 | A pass started at 10:00 with "OpenAI blog" active | Ana sets active = no at 10:01 | This pass still reads it. The pass list is fixed at its start. |

Questions    Q3 (H5) answered in S5 AC7-AC9

### S8. DeleteFeed: As the owner I want to delete a feed added by mistake so that the list stays clean

Rules        R10 a feed with stored articles cannot be deleted

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | "Batch" with 0 stored articles | Ana deletes it | FeedDeleted |
| AC2 | "OpenAI blog" with 12 stored articles | Ana deletes it | FeedDeleteRefused(has_articles). The 12 articles stay. |

Questions    none

### S4. StartIngestPass: As cron I want to start one pass per tick so that new articles are stored each 15 min

Rules        R3 one pass runs at a time (invariant, advisory lock)

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | No pass runs. 2 active feeds, 1 inactive | Cron starts a pass at 09:00 | IngestPassStarted. The pass list holds 2 feeds. |
| AC2 | The 09:00 pass holds the lock | Cron starts a pass at 09:15 | IngestPassSkipped. Exit code 0. One log line. |
| AC3 | Two ticks start at the same second | Both try the lock | One IngestPassStarted, one IngestPassSkipped. 1 + 1 = 2 passes > 1 allowed. |
| AC4 | The 09:00 pass process died | Cron starts a pass at 09:15 | IngestPassStarted. Postgres freed the lock when the dead session closed. |
| AC5 | No active feeds | Cron starts a pass | IngestPassStarted, then IngestPassCompleted with ok 0, failed 0, new 0. |

Questions    none

### S5. ReadFeed: As the ingest pass I want to read one feed so that its items reach the store

Rules        R4 a feed answers with HTTP 2xx within 10 s
             R5 the body is RSS 2.0 or Atom
             R11 failing_since holds the start of the current failure run

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | "The Batch" returns 200 with 3 RSS items | The pass reads it | FeedFetched, FeedParsed with 3 items |
| AC2 | "OpenAI blog" sends no response for 10 s | The pass reads it | FeedFetchFailed(timeout). The pass reads the next feed. |
| AC3 | "OpenAI blog" returns 503 | The pass reads it | FeedFetchFailed(http_503) |
| AC4 | "OpenAI blog" returns 200 with an HTML page | The pass reads it | FeedParseFailed |
| AC5 | "The Batch" returns 200 with an Atom feed of 0 entries | The pass reads it | FeedParsed with 0 items |
| AC6 | "The Batch" fails, "OpenAI blog" returns 2 new items | The pass reads both | 2 ArticleStored. 1 feed failed. |
| AC7 | "OpenAI blog" ok until now | It times out at 26 Oct 09:15 | last_status fetch_failed, failing_since 26 Oct 09:15 |
| AC8 | "OpenAI blog" failing since 26 Oct 09:15 | It times out again at 09:30 | failing_since stays 26 Oct 09:15 |
| AC9 | "OpenAI blog" failing since 26 Oct 09:15 | It returns 200 with valid RSS at 29 Oct 10:00 | last_status ok, failing_since empty |
| AC10 | "OpenAI blog" sends 1 byte each 2 s | The pass reads it | FeedFetchFailed(timeout) at 10 s total |
| AC11 | "OpenAI blog" returns a 6 MB body | The pass reads it | FeedFetchFailed(too_large) at 5 MB |

Questions    none

### S6. IngestArticle: As the ingest pass I want to store each new item once so that the store has no duplicates

Rules        R6 one article per canonical URL (invariant, unique key)
             R7 an item link is an absolute http or https URL
             R8 canonical URL: lower-case scheme and host, no fragment, no tracking parameter (D19), no trailing slash

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | Empty store | Item link `https://Example.com/gpt-6/?utm_source=rss&id=7#top` | ArticleStored with canonical URL `https://example.com/gpt-6?id=7` |
| AC2 | Stored `https://example.com/gpt-6` | Item link `https://example.com/gpt-6/` from another feed | DuplicateArticleSkipped. The first copy keeps its title. |
| AC3 | Empty store | One feed gives the same link twice in one body | 1 ArticleStored, 1 DuplicateArticleSkipped |
| AC4 | Empty store | Two writers insert `https://example.com/a` at once | 1 row. 1 + 1 = 2 rows > 1 allowed. The unique key refuses the second. |
| AC5 | Empty store | Item with no link | ArticleRejected(link_missing) |
| AC6 | Empty store | Item link `/news/42` | ArticleRejected(link_not_absolute) |
| AC7 | Stored at 09:10, published 09:00 | The metric query runs | The article counts as stored under 30 min. |
| AC8 | Item link `https://example.com/a?b=2&a=1` | Canonicalised | `https://example.com/a?b=2&a=1`. Parameter order stays. |
| AC9 | Empty store | Item with no published date | ArticleStored with published_at empty |
| AC10 | Fetch at 09:00 | Item with published date 12:00 the same day | ArticleStored with published_at 12:00, as given |
| AC11 | Empty store | Item link `https://example.com/a?fbclid=x&gclid=y&mc_cid=z&ref=hn` | ArticleStored with canonical URL `https://example.com/a?ref=hn` |

Questions    Q4 (H3), Q5 (H4), Q6 (H9). H6 is answered by AC3 and AC4.

### S7. CompleteIngestPass: As the ingest pass I want to write a run record so that the owner sees what each pass did

Rules        none

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | A pass read 20 feeds: 19 ok, 1 failed, 42 new articles | The pass ends | IngestPassCompleted with ok 19, failed 1, new 42. The lock is free. |
| AC2 | A pass stored 5 articles, then the process died | The owner opens run records | The record shows started, no finished time. The 5 articles stay. |

Questions    H7 crash with an open run record: tech, at step ⑤
             H8 slow body read past 10 s: tech, at step ⑤

### V1. Metric: As the owner I want one number per period so that I can drop or promote

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | 1,200 articles: 1,150 under 30 min, 36 at 30 min or more, 14 with no date | The owner runs the metric | on time 1,150 of 1,186 = 97.0%, excluded 14 |
| AC2 | Published 12:00, stored 09:05 | The owner runs the metric | Excluded: published more than 5 min after stored |
| AC3 | Any store | The owner runs the metric | Duplicate canonical URLs: 0 |

## Failure checklist

| Check | Answer |
|---|---|
| Crash between steps | An article write is its own transaction. Articles stored before a crash stay. The run record stays open (S7 AC2). |
| Retries and duplicates | No retry in a pass. The next tick reads the feed again. The unique key makes a second store a skip (S6 AC2). |
| Ordering and concurrency | One pass at a time (S4 AC3). Two writers on one URL (S6 AC4). |
| Poison input | Bad XML (S5 AC4). Bad link (S6 AC5, AC6). Huge body: H8. |
| An event with no command | E16 crash, E17 trial end. Both listed in `eventstorm.md`. |
| An owner per decision | The owner decides feeds and the trial. The pass decides nothing else. |

## Questions

| Q | Command | Question | Status | Decision |
|---|---|---|---|---|
| Q1 | S1 | Can two feeds have the same URL? | answered | No. Unique, exact match (D14). |
| Q2 | S8 | The owner deletes a feed with stored articles. What happens to the articles? | answered | Delete refused. Turn the feed off (D15). |
| Q3 | S5 | Where does the owner see a feed that fails on many ticks? | answered | Feed health fields in the admin list (D16). |
| Q4 | S6 | An item has no published date. Store it or reject it? | answered | Stored, excluded from the metric (D17). |
| Q5 | S6 | An item has a published date in the future. Keep it as given? | answered | Stored as given, excluded from the metric (D18). |
| Q6 | S6 | Remove `utm_*` only, or other trackers too? | answered | Fixed list of five trackers (D19). |

## Out of scope

Feed admin beyond Django admin. Conditional GET. Full-text scraping. Same story on two URLs. LLM summary or tags. Retries in a pass. Alerts. A read API.
