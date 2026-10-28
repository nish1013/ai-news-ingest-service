import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0002_feed_url_unique"),
    ]

    operations = [
        migrations.AlterField(
            model_name="article",
            name="canonical_url",
            field=models.TextField(),
        ),
        migrations.AddConstraint(
            model_name="article",
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.MD5("canonical_url"),
                name="article_canonical_url_unique",
            ),
        ),
    ]
