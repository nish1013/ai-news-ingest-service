# Brief: AI news ingest worker

> "Crate a simple ingest worker"

A scheduled job pulls AI news feeds and stores each article once.

## Brief

| Field | Content |
|---|---|
| Goal | A simple worker ingests AI news into one store. |
| Metric | Articles with `stored_at - published_at` under 30 min: 95% or more. Duplicate articles per canonical URL: 0. (assumed) |
| User | The owner of an AI news digest who reads the stored articles each day. (assumed) |
| Now | The owner opens each news site or feed reader by hand. (assumed) |
| Constraints | Python with Django. Postgres. RSS and Atom feeds in a `Feed` table. One run each 15 min. |
| Architecture | Hexagonal (ports and adapters). The domain is plain Python and imports no Django. |
| Stage | `mvp`. It is a new idea. The metric decides drop or promote. |
| Risk tier | `reversible`. Public feed data only. No personal data, no money. |

## Pushback

| Plan says | Concern | I would instead |
|---|---|---|
| "worker" | A long-running daemon needs its own scheduler, restart logic and health check. | Cron runs one Django management command per tick. It exits. A lock stops two passes at once. |

## Scope

| In | Cut | Why |
|---|---|---|
| `Feed` table with name, URL and active flag, edited in Django admin | Custom feed UI or API | Django admin gives the edit screen with no build work. |
| Fetch each feed, with a 10 s timeout | Conditional GET (ETag, Last-Modified) | 15-min polls of 20 feeds are cheap. |
| Parse RSS 2.0 and Atom into one article shape | Full-text scraping of article pages | Title, link, date and summary prove the flow. |
| Canonical URL: lower-case host, no fragment, no `utm_*`, no trailing slash | Near-duplicate stories across sources | Same-story matching needs an LLM or a similarity score. |
| One stored article per canonical URL | LLM summary, tags, ranking | Those are consumers of this store. |
| A failed feed does not stop the other feeds | Retry with backoff inside a pass | The next tick in 15 min is the retry. |
| One run record per pass: feeds ok, feeds failed, articles new | Metrics stack, alerts | Logs are enough at `mvp`. |
| A Postgres advisory lock allows one pass at a time | Read API for consumers | Consumers read the table directly. |

## Stop condition

After 14 days of runs, the metric is under 95%. Then drop, or fix the feed list and run 14 more days.
