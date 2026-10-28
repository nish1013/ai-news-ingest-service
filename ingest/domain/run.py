"""Run record values."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RunCounts:
    """What one ingest pass did."""

    feeds_ok: int
    feeds_failed: int
    articles_new: int
