import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Feed",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                ("url", models.CharField(max_length=2000)),
                ("active", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="RunRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("started_at", models.DateTimeField()),
                ("finished_at", models.DateTimeField(null=True)),
                ("feeds_ok", models.PositiveIntegerField(default=0)),
                ("feeds_failed", models.PositiveIntegerField(default=0)),
                ("articles_new", models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name="Article",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("canonical_url", models.CharField(max_length=2000)),
                ("title", models.TextField()),
                ("published_at", models.DateTimeField(null=True)),
                ("stored_at", models.DateTimeField(auto_now_add=True)),
                (
                    "feed",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="articles",
                        to="ingest.feed",
                    ),
                ),
            ],
        ),
    ]
