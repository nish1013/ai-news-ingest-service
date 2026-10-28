from io import StringIO

import pytest
from django.core.management import call_command

from ingest.adapters.orm.models import Article, Feed, RunRecord
from ingest.domain.feed import FeedItem
from tests.feed_server import feed_server, rss


@pytest.mark.django_db
def test_s4_ac1_pass_reads_the_two_active_feeds_only() -> None:
    with feed_server() as server:
        for slug, active in (("batch", True), ("openai", True), ("old", False)):
            item = FeedItem(
                link=f"https://example.com/{slug}/1", title=slug, published_at=None
            )
            url = server.serve(f"/{slug}.xml", rss([item]))
            Feed.objects.create(name=slug, url=url, active=active)
        out = StringIO()

        call_command("ingest_feeds", stdout=out)

    assert sorted(server.requested_paths) == ["/batch.xml", "/openai.xml"]
    assert sorted(Article.objects.values_list("canonical_url", flat=True)) == [
        "https://example.com/batch/1",
        "https://example.com/openai/1",
    ]
    record = RunRecord.objects.get()
    assert (record.feeds_ok, record.feeds_failed, record.articles_new) == (2, 0, 2)
    assert out.getvalue() == "Pass completed: 2 feeds ok, 0 failed, 2 new articles\n"
