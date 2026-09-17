from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0049_malaccount_full_sync_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="malaccount",
            name="sync_filter_watched",
            field=models.BooleanField(
                default=True,
                help_text="Include Completed/In Progress entries in a full sync to MyAnimeList",
            ),
        ),
        migrations.AddField(
            model_name="malaccount",
            name="sync_filter_dropped",
            field=models.BooleanField(
                default=True,
                help_text="Include Dropped entries in a full sync to MyAnimeList",
            ),
        ),
        migrations.AddField(
            model_name="malaccount",
            name="sync_filter_rated_only",
            field=models.BooleanField(
                default=False,
                help_text="Only include entries that have a score set in a full sync to MyAnimeList",
            ),
        ),
    ]
