from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0003_article_canonical_url_unique"),
    ]

    operations = [
        migrations.AlterField(
            model_name="article",
            name="stored_at",
            field=models.DateTimeField(),
        ),
    ]
