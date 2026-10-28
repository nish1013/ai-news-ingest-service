# Plan: AI news ingest worker, mvp

Status: locked, 2026-10-28

Six PRs. PR1 is a thin slice from a registered feed to a stored article. Scope: `mvp`.

## Stack

| Layer | Pick | Why |
|---|---|---|
| Language | Python 3.12 | Supported until 2028. Django 5.2 supports it. |
| Framework | Django 5.2 LTS | Security fixes until April 2028. Admin gives the feed screens (D5). |
| Database | Postgres 16, `psycopg` 3 | Unique keys and advisory locks (R3, R6). |
| HTTP | `httpx` | Streamed body with a total deadline and a size cap (S5 AC10, AC11). |
| Feed parsing | `feedparser` | RSS 2.0 and Atom (D8). Fed bytes, never a URL. |
| Layers check | `import-linter` | Fails CI when `domain` imports Django, `httpx` or `feedparser` (D7). |
| Tests | `pytest`, `pytest-django` | One runner for unit and integration tests. |
| Quality | `black`, `ruff`, `mypy` with `django-stubs` | Black at line length 88. Type hints on public functions, checked. |
| Local run | Docker Compose: Postgres only | The app runs on the host with `manage.py`. |
| CI | GitHub Actions with a Postgres 16 service | One job runs the same command as local. |
| Schedule | Host crontab, one line in the README | D1. No scheduler in the app. |

Each package pins a version released before 2026-10-14.

## Layout

```
ingest/                     one Django app, one context
  domain/                   plain Python: values, rules, Feed, errors. No Django import.
  application/              use cases: IngestPass, FeedCommands. Ports as Protocols.
  adapters/
    orm/                    models, FeedCatalog, ArticleStore, RunLog
    postgres_lock.py        PassLock
    feed_reader.py          FeedReader: httpx + feedparser
    admin.py                Django admin, calls FeedCommands
  management/commands/      ingest_feeds, ingest_metric
```

## PR series

| PR | Delivers | Criteria | Proves | Risk |
|---|---|---|---|---|
| PR1 | Thin slice: skeleton, CI, layers contract, one feed to one stored article | S1 AC1, S4 AC1, S5 AC1, S6 AC1, S7 AC1 | | normal: no rule two requests can break |
| PR2 | Feed rules in admin: URL checks, unique URL, on and off, protected delete | S1 AC2-AC5, S2 AC1-AC4, S3 AC1-AC2, S8 AC1-AC2 | R1, R9, R10 | high: R10 race |
| PR3 | Canonical URL and one article per URL | S6 AC2-AC11 | R6, R7, R8 | high: R6 race |
| PR4 | Feed failures and feed health in admin | S5 AC2-AC11 | R4, R5, R11 | normal: one feed row per update |
| PR5 | One pass at a time, fixed feed list, crash safety | S3 AC3, S4 AC2-AC5, S7 AC2 | R3 | high: R3 race |
| PR6 | Metric command and operating notes in the README | V1 AC1-AC3 | | normal: read only |

## Tests

| Level | What | Database |
|---|---|---|
| Unit | `CanonicalUrl`, `FeedUrl`, `FetchFailure`, feed health rules, IngestPass with in-memory adapters | none |
| Integration | ORM adapters, unique keys, advisory lock, admin through the Django test client | Postgres |
| Contract | FeedReader: one suite runs against the stub and the real adapter on a local `http.server` | none |
| Race | R3, R6, R10: two connections at once. Each test fails with its guard removed. | Postgres |

One command, local and CI: `make check` runs black, ruff, mypy, `lint-imports` and `pytest`.

## Verification

```
docker compose up -d db
make check
python manage.py ingest_feeds
python manage.py ingest_metric --days 14
```

## Deviations
