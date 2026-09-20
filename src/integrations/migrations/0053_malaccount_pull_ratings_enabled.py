from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0052_malaccount_split_sync_filters"),
    ]

    operations = [
        migrations.AddField(
            model_name="malaccount",
            name="pull_ratings_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Adopt a MyAnimeList rating locally when Floppy doesn't have one recorded",
            ),
        ),
    ]
