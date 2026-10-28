"""Clock adapter: the system clock in UTC."""

from datetime import UTC, datetime


class SystemClock:
    """The current time from the system clock."""

    def now(self) -> datetime:
        """Return the current time in UTC."""
        return datetime.now(UTC)
