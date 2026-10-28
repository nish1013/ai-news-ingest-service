import pytest
from django.test import Client

from ingest.adapters.orm.models import Feed


@pytest.mark.django_db
def test_s1_ac1_registered_feed_is_active(admin_client: Client) -> None:
    response = admin_client.post(
        "/admin/ingest/feed/add/",
        {"name": "The Batch", "url": "https://www.deeplearning.ai/the-batch/feed/"},
    )

    assert response.status_code == 302
    feed = Feed.objects.get()
    assert (feed.name, feed.url, feed.active) == (
        "The Batch",
        "https://www.deeplearning.ai/the-batch/feed/",
        True,
    )
