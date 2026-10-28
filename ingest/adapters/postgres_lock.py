"""PassLock adapter: a Postgres session advisory lock with one fixed key."""

from django.db import connection

PASS_LOCK_KEY = 7_211_001


class PostgresPassLock:
    """Lets one ingest pass run at a time across processes."""

    def acquire(self) -> None:
        """Take the lock. Waits while another session holds it."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [PASS_LOCK_KEY])

    def release(self) -> None:
        """Free the lock."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [PASS_LOCK_KEY])
