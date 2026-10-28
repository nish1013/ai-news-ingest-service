from django.apps import AppConfig


class IngestConfig(AppConfig):
    name = "ingest"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from ingest.adapters import admin  # noqa: F401
