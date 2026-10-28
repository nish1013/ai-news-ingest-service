"""The on-time metric: its limits and the counts of one period."""

from dataclasses import dataclass
from datetime import timedelta

ON_TIME_LIMIT = timedelta(minutes=30)
FUTURE_DATE_TOLERANCE = timedelta(minutes=5)
EXCLUDED_LIMIT_PERCENT = 5


@dataclass(frozen=True)
class OnTimeMetric:
    """The article counts of one period.

    `counted` holds the articles with a usable published date. `excluded` holds
    the rest: no date, or a date over FUTURE_DATE_TOLERANCE after `stored_at`.
    """

    on_time: int
    counted: int
    excluded: int
    duplicate_urls: int

    @property
    def total(self) -> int:
        """Return the counted and the excluded articles together."""
        return self.counted + self.excluded

    @property
    def percent(self) -> float | None:
        """Return the on-time share of the counted articles, or None for none."""
        if not self.counted:
            return None
        return self.on_time * 100 / self.counted

    @property
    def valid(self) -> bool:
        """Return False when over EXCLUDED_LIMIT_PERCENT of the total is excluded."""
        return self.excluded * 100 <= self.total * EXCLUDED_LIMIT_PERCENT
