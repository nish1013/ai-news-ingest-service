"""Django model discovery. The models live in the ORM adapter."""

from ingest.adapters.orm.models import Article, Feed, RunRecord

__all__ = ["Article", "Feed", "RunRecord"]
