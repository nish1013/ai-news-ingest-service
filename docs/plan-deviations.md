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
- **Built:** `on_time_articles()` in `ingest/adapters/orm/queries.py` returns articles with a published date and `stored_at` under 30 min after it. `ON_TIME_LIMIT` in the domain holds the 30 min.
- **Why:** No metric query exists before PR 6. The query holds only the on-time rule. The exclusions of D17 and D18 belong to S9 AC1 and AC2.
- **Undo:** Move the query into the PR 6 metric command and point the S6 AC7 test at that command.
