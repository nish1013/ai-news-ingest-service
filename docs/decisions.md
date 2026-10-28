# Decisions

Each row is dated and written when the decision is made.

| # | Kind | Decision | Why | Alternatives considered | Consequence |
|---|---|---|---|---|---|
| D1 | product | 2026-10-28. Cron runs one `ingest_feeds` pass each 15 min. The pass exits when done. | A one-shot command needs no in-process timer, restart logic or health check. | A long-running worker with its own timer: more ops for the same result. | A Postgres advisory lock must stop two passes at once. |
| D2 | product | 2026-10-28. Store one article per canonical URL. Same story on two URLs stays two rows. | Same-story matching needs an LLM or a similarity score. That is not the `mvp` bet. | Title similarity dedup: false merges on short titles like "GPT-6 is out". | A consumer can see the same story twice from two sources. |
| D3 | product | 2026-10-28. Metric: 95% of articles stored under 30 min after `published_at`. 0 duplicate canonical URLs. (assumed) | Both values come from one query on the article table. | Count of articles per day: it grows with feeds, not with quality. | A feed with wrong `published_at` values moves the metric. Exclude it in the query. |
| D4 | product | 2026-10-28. The user is the owner of an AI news digest. (assumed) | No other role reads the store at `mvp`. | Downstream services as the user: none exists yet. | The stop condition reads the metric only. |
| D5 | product | 2026-10-28. Feeds live in a `Feed` table, edited in Django admin. | Django admin gives the edit screen with no build work. | A config file in the repo: each new feed needs a deploy. | The pass reads active `Feed` rows at its start. |
| D6 | tech | 2026-10-28. Python, Django and Postgres. | Owner choice. | TypeScript on Node. | Django ORM and admin are adapters, never domain code. |
| D7 | tech | 2026-10-28. Hexagonal architecture. The domain imports no Django, no feedparser and no HTTP. | Domain rules get tests with no database or network. | Django apps with logic in models and views: tests need the database. | One mapping per ORM model. An `import-linter` contract fails CI on a wrong import. |
| D8 | tech | 2026-10-28. `feedparser` reads RSS and Atom. `import-linter` checks the layers. | Both checked on PyPI: maintained since 2007 and 2019, source repos public. | Own XML parser: many feed format edge cases. | `feedparser` lives in the FeedReader adapter only. |
