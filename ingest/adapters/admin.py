"""Django admin for feeds. Each change goes through FeedCommands."""

from typing import Any

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import F, QuerySet
from django.http import HttpRequest

from ingest.adapters.orm.models import Feed, RunRecord
from ingest.adapters.orm.stores import DjangoFeedCatalog
from ingest.application.feed_commands import (
    FeedCommands,
    FeedDeleteRefused,
    FeedEdited,
    FeedRegistered,
    FeedRejected,
)
from ingest.domain.feed import FeedRuleReason

_RULE_ERRORS = {
    FeedRuleReason.URL_SCHEME: ("url", "Enter an absolute http or https URL."),
    FeedRuleReason.URL_MISSING: ("url", "Enter the feed URL."),
    FeedRuleReason.NAME_MISSING: ("name", "Enter the feed name."),
    FeedRuleReason.URL_TAKEN: ("url", "Another feed has this URL."),
}


class FeedForm(forms.ModelForm):
    """Feed form. Its clean step runs FeedCommands, which decide each feed rule."""

    name = forms.CharField(max_length=200, required=False)
    url = forms.CharField(label="URL", max_length=2000, required=False)

    class Meta:
        model = Feed
        fields = ("name", "url", "active")

    def clean(self) -> dict[str, Any]:
        """Run the feed command. A broken rule becomes a field error."""
        cleaned = super().clean() or {}
        if not self.errors:
            self._run_commands(cleaned)
        return cleaned

    def validate_unique(self) -> None:
        """Leave the unique URL rule to FeedCommands and its unique key."""

    def _run_commands(self, cleaned: dict[str, Any]) -> None:
        commands = _commands()
        name, url = cleaned["name"], cleaned["url"]
        result: FeedRegistered | FeedEdited | FeedRejected | None = None
        if self.instance.pk is None:
            result = commands.register(name=name, url=url)
        elif {"name", "url"} & set(self.changed_data):
            result = commands.edit(self.instance.pk, name=name, url=url)
        if isinstance(result, FeedRejected):
            field, message = _RULE_ERRORS[result.reason]
            self.add_error(field, message)
            return
        if isinstance(result, FeedRegistered):
            self.instance = Feed.objects.get(pk=result.feed_id)
        elif "active" in self.changed_data:
            commands.set_active(self.instance.pk, active=cleaned["active"])


@admin.register(Feed)
class FeedAdmin(admin.ModelAdmin):
    """Feed list and form. A new feed is active, so the add form hides the flag.

    The list shows feed health, failing feeds first (D16).
    """

    form = FeedForm
    list_display = (
        "name",
        "url",
        "active",
        "last_status",
        "last_read_at",
        "failing_since",
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[Feed]:
        """Return the feeds, failing feeds first, the longest failing at the top."""
        return (
            super()
            .get_queryset(request)
            .order_by(F("failing_since").asc(nulls_last=True), "name")
        )

    def get_fields(
        self, request: HttpRequest, obj: Feed | None = None
    ) -> tuple[str, ...]:
        """Return the form fields: no active flag on add."""
        if obj is None:
            return ("name", "url")
        return ("name", "url", "active")

    def save_model(
        self, request: HttpRequest, obj: Feed, form: forms.Form, change: bool
    ) -> None:
        """Store nothing: FeedForm stored the feed through FeedCommands."""

    def delete_model(self, request: HttpRequest, obj: Feed) -> None:
        """Delete the feed through FeedCommands."""
        if isinstance(_commands().delete(obj.pk), FeedDeleteRefused):
            raise PermissionDenied("The feed has stored articles. Turn it off.")

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[Feed]) -> None:
        """Delete each feed through FeedCommands."""
        for feed in queryset:
            self.delete_model(request, feed)


@admin.register(RunRecord)
class RunRecordAdmin(admin.ModelAdmin):
    """Run records, newest first. Only the pass writes them."""

    list_display = (
        "started_at",
        "finished_at",
        "feeds_ok",
        "feeds_failed",
        "articles_new",
        "unfinished",
    )
    ordering = ("-started_at",)

    @admin.display(boolean=True, description="Unfinished")
    def unfinished(self, obj: RunRecord) -> bool:
        """Return True when the pass wrote no finished time."""
        return obj.finished_at is None

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Refuse: only the pass adds run records."""
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: RunRecord | None = None
    ) -> bool:
        """Refuse: only the pass changes run records."""
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: RunRecord | None = None
    ) -> bool:
        """Refuse: run records are the history of the passes."""
        return False


def _commands() -> FeedCommands:
    return FeedCommands(DjangoFeedCatalog())
