from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0051_malaccount_per_item_sync_enabled"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="malaccount",
            name="sync_filter_watched",
        ),
        migrations.AddField(
            model_name="malaccount",
            name="sync_filter_completed",
            field=models.BooleanField(
                default=True,
                help_text="Include Completed entries in a full sync to MyAnimeList",
            ),
        ),
        migrations.AddField(
            model_name="malaccount",
            name="sync_filter_in_progress",
            field=models.BooleanField(
                default=True,
                help_text="Include In Progress entries in a full sync to MyAnimeList",
            ),
        ),
        migrations.AddField(
            model_name="malaccount",
            name="sync_ratings_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Include the score/rating when pushing status to MyAnimeList",
            ),
        ),
        migrations.AddField(
            model_name="malaccount",
            name="pull_higher_progress_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Adopt MyAnimeList's progress locally when it's ahead of Floppy's own record",
            ),
        ),
    ]
