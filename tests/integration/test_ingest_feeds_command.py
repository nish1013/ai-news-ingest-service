from io import StringIO

import pytest
from django.core.management import call_command

from ingest.adapters.orm.models import Article, Feed, RunRecord
from ingest.domain.feed import FeedItem
from tests.feed_server import Reply, feed_server, rss


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


@pytest.mark.django_db
def test_s5_ac6_one_feed_fails_and_the_other_stores_two_new_items() -> None:
    with feed_server() as server:
        batch_url = server.reply("/batch.xml", Reply(body=b"down", status=503))
        items = [
            FeedItem(
                link=f"https://openai.com/blog/{n}",
                title=f"Post {n}",
                published_at=None,
            )
            for n in (1, 2)
        ]
        openai_url = server.serve("/openai.xml", rss(items))
        batch = Feed.objects.create(name="The Batch", url=batch_url)
        Feed.objects.create(name="OpenAI blog", url=openai_url)
        out = StringIO()

        call_command("ingest_feeds", stdout=out)

    assert Article.objects.count() == 2
    record = RunRecord.objects.get()
    assert (record.feeds_ok, record.feeds_failed, record.articles_new) == (1, 1, 2)
    batch.refresh_from_db()
    assert batch.last_status == "fetch_failed"
    assert out.getvalue() == "Pass completed: 1 feeds ok, 1 failed, 2 new articles\n"
