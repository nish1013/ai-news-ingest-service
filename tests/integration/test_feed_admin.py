import pytest
from django.test import Client

from ingest.adapters.orm.models import Article, Feed

ADD_URL = "/admin/ingest/feed/add/"
BATCH_URL = "https://www.deeplearning.ai/the-batch/feed/"
OPENAI_URL = "https://openai.com/blog/rss.xml"


def _change_url(feed: Feed) -> str:
    return f"/admin/ingest/feed/{feed.id}/change/"


def _form_errors(response: object) -> dict[str, list[str]]:
    return dict(response.context["adminform"].form.errors)  # type: ignore[attr-defined]


def _change(client: Client, feed: Feed, **values: str) -> object:
    data = {"name": feed.name, "url": feed.url}
    if feed.active:
        data["active"] = "on"
    data.update(values)
    return client.post(_change_url(feed), {k: v for k, v in data.items() if v})


@pytest.mark.django_db
def test_s1_ac1_registered_feed_is_active(admin_client: Client) -> None:
    response = admin_client.post(ADD_URL, {"name": "The Batch", "url": BATCH_URL})

    assert response.status_code == 302
    feed = Feed.objects.get()
    assert (feed.name, feed.url, feed.active) == ("The Batch", BATCH_URL, True)


@pytest.mark.django_db
def test_s1_ac2_admin_shows_the_url_scheme_error(admin_client: Client) -> None:
    response = admin_client.post(ADD_URL, {"name": "Bad", "url": "ftp://x.org/feed"})

    assert _form_errors(response) == {"url": ["Enter an absolute http or https URL."]}
    assert not Feed.objects.exists()


@pytest.mark.django_db
def test_s1_ac3_admin_shows_the_url_missing_error(admin_client: Client) -> None:
    response = admin_client.post(ADD_URL, {"name": "Empty", "url": ""})

    assert _form_errors(response) == {"url": ["Enter the feed URL."]}
    assert not Feed.objects.exists()


@pytest.mark.django_db
def test_s1_ac4_admin_shows_the_name_missing_error(admin_client: Client) -> None:
    response = admin_client.post(ADD_URL, {"name": "  ", "url": BATCH_URL})

    assert _form_errors(response) == {"name": ["Enter the feed name."]}
    assert not Feed.objects.exists()


@pytest.mark.django_db
def test_s1_ac5_admin_shows_the_url_taken_error(admin_client: Client) -> None:
    Feed.objects.create(name="The Batch", url=BATCH_URL)

    response = admin_client.post(ADD_URL, {"name": "Batch", "url": BATCH_URL})

    assert _form_errors(response) == {"url": ["Another feed has this URL."]}
    assert Feed.objects.count() == 1


@pytest.mark.django_db
def test_s2_ac1_admin_stores_the_new_url(admin_client: Client) -> None:
    feed = Feed.objects.create(name="OpenAI blog", url="https://openai.com/rss")

    response = _change(admin_client, feed, url=OPENAI_URL)

    assert response.status_code == 302  # type: ignore[attr-defined]
    feed.refresh_from_db()
    assert (feed.name, feed.url, feed.active) == ("OpenAI blog", OPENAI_URL, True)


@pytest.mark.django_db
def test_s2_ac2_admin_shows_the_url_scheme_error(admin_client: Client) -> None:
    feed = Feed.objects.create(name="OpenAI blog", url=OPENAI_URL)

    response = _change(admin_client, feed, url="openai.com/blog")

    assert _form_errors(response) == {"url": ["Enter an absolute http or https URL."]}
    feed.refresh_from_db()
    assert feed.url == OPENAI_URL


@pytest.mark.django_db
def test_s2_ac4_admin_shows_the_url_taken_error(admin_client: Client) -> None:
    Feed.objects.create(name="The Batch", url=BATCH_URL)
    feed = Feed.objects.create(name="OpenAI blog", url=OPENAI_URL)

    response = _change(admin_client, feed, url=BATCH_URL)

    assert _form_errors(response) == {"url": ["Another feed has this URL."]}
    feed.refresh_from_db()
    assert feed.url == OPENAI_URL


@pytest.mark.django_db
def test_s3_ac1_admin_turns_a_feed_off(admin_client: Client) -> None:
    feed = Feed.objects.create(name="OpenAI blog", url=OPENAI_URL)

    response = _change(admin_client, feed, active="")

    assert response.status_code == 302  # type: ignore[attr-defined]
    feed.refresh_from_db()
    assert feed.active is False


@pytest.mark.django_db
def test_s3_ac2_admin_turns_a_feed_on(admin_client: Client) -> None:
    feed = Feed.objects.create(name="OpenAI blog", url=OPENAI_URL, active=False)

    response = _change(admin_client, feed, active="on")

    assert response.status_code == 302  # type: ignore[attr-defined]
    feed.refresh_from_db()
    assert feed.active is True


@pytest.mark.django_db
def test_s8_ac1_admin_deletes_a_feed_with_no_articles(admin_client: Client) -> None:
    feed = Feed.objects.create(name="Batch", url=BATCH_URL)

    response = admin_client.post(
        f"/admin/ingest/feed/{feed.id}/delete/", {"post": "yes"}
    )

    assert response.status_code == 302
    assert not Feed.objects.exists()


@pytest.mark.django_db
def test_s8_ac2_admin_keeps_a_feed_with_articles(admin_client: Client) -> None:
    feed = Feed.objects.create(name="OpenAI blog", url=OPENAI_URL)
    for n in range(12):
        Article.objects.create(
            feed=feed, canonical_url=f"{OPENAI_URL}/{n}", title=f"Post {n}"
        )

    response = admin_client.post(
        f"/admin/ingest/feed/{feed.id}/delete/", {"post": "yes"}
    )

    assert response.status_code == 200
    assert Feed.objects.filter(id=feed.id).exists()
    assert Article.objects.filter(feed_id=feed.id).count() == 12
