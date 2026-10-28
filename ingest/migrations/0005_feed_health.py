from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0004_article_stored_at_from_clock"),
    ]

    operations = [
        migrations.AddField(
            model_name="feed",
            name="failing_since",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="feed",
            name="last_read_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="feed",
            name="last_status",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
    ]
