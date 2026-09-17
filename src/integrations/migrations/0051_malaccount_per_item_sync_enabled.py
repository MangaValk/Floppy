from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0050_malaccount_sync_filters"),
    ]

    operations = [
        migrations.AddField(
            model_name="malaccount",
            name="per_item_sync_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Push status/progress/score to MyAnimeList as each entry is edited",
            ),
        ),
    ]
