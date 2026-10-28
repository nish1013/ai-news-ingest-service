"""PassLock adapter: a Postgres session advisory lock with one fixed key."""

from django.db import connection

PASS_LOCK_KEY = 7_211_001


class PostgresPassLock:
    """Lets one ingest pass run at a time across processes.

    The lock belongs to the session, not to a transaction: per-feed commits keep it,
    and Postgres frees it when the session ends.
    """

    def try_acquire(self) -> bool:
        """Take the lock if it is free. Return False when another session holds it."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", [PASS_LOCK_KEY])
            row = cursor.fetchone()
        return bool(row and row[0])

    def release(self) -> None:
        """Free the lock."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [PASS_LOCK_KEY])
