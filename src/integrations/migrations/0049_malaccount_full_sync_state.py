from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0048_merge_0037_malaccount_0047_merge_20260910_1141"),
    ]

    operations = [
        migrations.AddField(
            model_name="malaccount",
            name="full_sync_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="malaccount",
            name="full_sync_failed",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="malaccount",
            name="full_sync_processed",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="malaccount",
            name="full_sync_results",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="malaccount",
            name="full_sync_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="malaccount",
            name="full_sync_status",
            field=models.CharField(
                choices=[
                    ("idle", "Not started"),
                    ("queued", "Queued"),
                    ("running", "Running"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                ],
                default="idle",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="malaccount",
            name="full_sync_succeeded",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="malaccount",
            name="full_sync_total",
            field=models.PositiveIntegerField(default=0),
        ),
    ]