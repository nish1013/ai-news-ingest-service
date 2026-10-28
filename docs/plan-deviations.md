# Plan deviations

Where the build departs from [plan.md](plan.md), and why. A deviation becomes a decision only once it is added to [decisions.md](decisions.md).

## D1. CI workflow moves to a last PR (PR 1, 2026-10-28)

**In short:** The GitHub Actions check arrives in one last PR, after the other six PRs.

- **Plan:** PR 1 delivers CI (Stack, row CI): GitHub Actions with a Postgres 16 service runs `make check`.
- **Built:** PR 1 has no workflow file. A last PR "CI" adds it after the end suite of the series.
- **Why:** The night build writes no CI or CD file. `make check` runs the same gates locally.
- **Undo:** Add `.github/workflows/check.yml` with a Postgres 16 service that runs `make check`.

## D2. feedparser pinned at 6.0.12 (PR 1, 2026-10-28)

**In short:** The feed parser stays one release behind the newest version before the cut-off date.

- **Plan:** Each package pins a version released before 2026-10-14 (Stack). The newest `feedparser` before that date is 6.0.14.
- **Built:** `requirements.txt` pins `feedparser==6.0.12` (2025-09-10). It depends on `sgmllib3k`, released in 2010.
- **Why:** 6.0.13 and later depend on `feedparser-sgmllib`, first released 2026-07-27 from the `python-syndication` org, not the feedparser repo. The dependency check could not confirm its owner. The package is 3 months old.
- **Undo:** Bump the pin to 6.0.14 after a registry check of `feedparser-sgmllib`: owner, age, source repo.

## D3. S6 AC7 proven by an on-time article query (PR 3, 2026-10-28)

**In short:** The on-time rule is a query on the article table, ahead of the metric command that prints it.

- **Plan:** PR 3 delivers S6 AC7: "The metric query runs. The article counts as stored under 30 min." PR 6 delivers the metric command (S9).
- **Built:** `on_time_articles()` in `ingest/adapters/orm/queries.py` returns articles stored under 30 min after their published date. Since PR 6 it shares one on-time filter with `on_time_metric()`, the D17 and D18 exclusions included.
- **Why:** No metric query existed before PR 6, so S6 AC7 needed its own query. PR 6 added the exclusions to that filter for S9 AC1 and AC2, and the metric command counts with it.
- **Undo:** Drop `on_time_articles()` and point the S6 AC7 test at `on_time_metric()` or the `ingest_metric` command.

## D4. Unique key on the MD5 of the canonical URL (PR 3, 2026-10-28)

**In short:** A hash of the link keeps one article per link for links of any length.

- **Plan:** The unique key is on `article.canonical_url` (aggregates.md, "Rule per command" IngestArticle row and the R6 row).
- **Built:** The unique constraint is on `MD5(canonical_url)`, with the same constraint name. `canonical_url` is a text column.
- **Why:** A link over 2000 characters raised `DataError` and stopped the pass. On a text column, a plain btree unique key refuses a 5000-character link with `ProgramLimitExceeded` (index row over 2704 bytes). Two different URLs with one MD5 count as one article, an accepted risk at mvp.
- **Undo:** Replace the expression constraint with a plain unique key on `canonical_url`. Cap the link length and reject longer links.

## D5. Feed read deadline leaves out DNS lookups (PR 4, 2026-10-28)

**In short:** A feed read can pass its 10 s deadline by the time its DNS lookups take.

- **Plan:** A feed read has a 10 s total deadline (decisions.md D20, S5 AC10). The plan names a streamed body with a total deadline (Stack, HTTP row).
- **Built:** Each request, redirects included, and then the body read get their timeouts set to the time left of the 10 s. After each body chunk, the reader checks the 10 s total and returns `timeout` when it is over.
- **Why:** `httpx` has no total deadline, and the DNS lookup has no timeout. Connect, headers and body therefore end by 10 s, but each DNS lookup of the read adds its own time (one per redirect hop). The bound is 10 s plus the DNS time.
- **Undo:** Run the read under a watchdog that closes the socket at 10 s total, and resolve DNS with a timeout. Then every read ends at 10 s.
