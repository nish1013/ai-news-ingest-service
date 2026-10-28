from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from django.db import connection

from ingest.adapters.postgres_lock import PASS_LOCK_KEY


@contextmanager
def other_session() -> Iterator[psycopg.Connection]:
    """Open a second Postgres session on the test database."""
    settings = connection.settings_dict
    with psycopg.connect(
        host=settings["HOST"],
        port=settings["PORT"],
        dbname=settings["NAME"],
        user=settings["USER"],
        password=settings["PASSWORD"],
        autocommit=True,
    ) as other:
        yield other


def take_pass_lock(session: psycopg.Connection) -> bool:
    row = session.execute(
        "SELECT pg_try_advisory_lock(%s)", (PASS_LOCK_KEY,)
    ).fetchone()
    return bool(row and row[0])


def pass_lock_is_free() -> bool:
    """Try the pass lock from a second Postgres session, then free it."""
    with other_session() as other:
        taken = take_pass_lock(other)
        if taken:
            other.execute("SELECT pg_advisory_unlock(%s)", (PASS_LOCK_KEY,))
        return taken
