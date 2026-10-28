import psycopg
from django.db import connection

from ingest.adapters.postgres_lock import PASS_LOCK_KEY


def pass_lock_is_free() -> bool:
    """Try the pass lock from a second Postgres session, then free it."""
    settings = connection.settings_dict
    with psycopg.connect(
        host=settings["HOST"],
        port=settings["PORT"],
        dbname=settings["NAME"],
        user=settings["USER"],
        password=settings["PASSWORD"],
        autocommit=True,
    ) as other:
        row = other.execute(
            "SELECT pg_try_advisory_lock(%s)", (PASS_LOCK_KEY,)
        ).fetchone()
        taken = bool(row and row[0])
        if taken:
            other.execute("SELECT pg_advisory_unlock(%s)", (PASS_LOCK_KEY,))
        return taken
