from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0002_feed_url_unique"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="article",
            constraint=models.UniqueConstraint(
                fields=("canonical_url",), name="article_canonical_url_unique"
            ),
        ),
    ]
