"""PassLock adapter: a Postgres session advisory lock with one fixed key."""

PASS_LOCK_KEY = 7_211_001


class PostgresPassLock:
    """Lets one ingest pass run at a time across processes."""

    def acquire(self) -> None:
        """Take the lock."""
        raise NotImplementedError

    def release(self) -> None:
        """Free the lock."""
        raise NotImplementedError
