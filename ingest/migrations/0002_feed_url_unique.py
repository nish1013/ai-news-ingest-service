from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="feed",
            constraint=models.UniqueConstraint(fields=("url",), name="feed_url_unique"),
        ),
    ]
