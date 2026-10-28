"""Django admin for feeds."""

from django.contrib import admin
from django.http import HttpRequest

from ingest.adapters.orm.models import Feed


@admin.register(Feed)
class FeedAdmin(admin.ModelAdmin):
    """Feed list and form. A new feed is active, so the add form hides the flag."""

    list_display = ("name", "url", "active")

    def get_fields(
        self, request: HttpRequest, obj: Feed | None = None
    ) -> tuple[str, ...]:
        """Return the form fields: no active flag on add."""
        if obj is None:
            return ("name", "url")
        return ("name", "url", "active")
