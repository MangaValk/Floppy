"""Contracts for disposable benchmark data and portable exports."""

import gzip
import importlib.util
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from app import models
from app.benchmark_data import TRACKERS, build_dataset
from integrations.models import ImportRun
from users.models import User

spec = importlib.util.spec_from_file_location(
    "benchmark_fixtures",
    Path(__file__).resolve().parents[3] / "scripts/benchmark_fixtures.py",
)
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


class BenchmarkFixtureTests(TestCase):
    def test_coverage_and_portable_round_trip(self):
        with (
            patch(
                "requests.sessions.Session.request",
                side_effect=AssertionError("Provider I/O"),
            ),
            patch(
                "celery.app.task.Task.apply_async",
                side_effect=AssertionError("Task dispatch"),
            ),
        ):
            exported = build_dataset(100, 1729)
        self.assertEqual(sum(model.objects.count() for model in set(TRACKERS)), 100)
        self.assertEqual(User.objects.count(), 3)
        self.assertTrue(
            all(not user.has_usable_password() for user in User.objects.all())
        )
        self.assertEqual(models.Episode.objects.count(), 240)
        self.assertEqual(models.Episode.history.count(), 480)
        self.assertEqual(models.Item.objects.count(), 220)
        self.assertEqual(models.CollectionEntry.objects.count(), 40)
        self.assertEqual(ImportRun.objects.count(), 3)
        self.assertEqual(
            sum(ImportRun.objects.values_list("created_count", flat=True)), 50
        )
        self.assertEqual(
            set(models.Movie.objects.values_list("status", flat=True)),
            set(models.Status.values),
        )
        for entry in models.CollectionEntry.objects.all():
            field = models.CollectionField.objects.get(
                pk=next(iter(entry.custom_field_values))
            )
            self.assertEqual(field.group.user_id, entry.user_id)
        for episode in models.Episode.objects.select_related(
            "item", "related_season__item"
        ):
            self.assertEqual(
                episode.item.media_id, episode.related_season.item.media_id
            )
            self.assertEqual(episode.item.season_number, 1)
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture.json.gz"
            checksum = harness.export_fixture(exported, fixture)
            self.assertEqual(checksum, harness.export_fixture(exported, fixture))
            with gzip.open(fixture, "rt") as stream:
                records = json.load(stream)
            self.assertEqual(
                len(records), sum(model.objects.count() for model in exported)
            )
            for model in reversed(exported):
                model.objects.all().delete()
            call_command("loaddata", str(fixture), verbosity=0, stdout=io.StringIO())
            self.assertEqual(checksum, harness.export_fixture(exported, fixture))

    def test_refuses_existing_data_and_invalid_sizes(self):
        for size in (0, 9, 11):
            with self.assertRaisesMessage(ValueError, "multiple of 10"):
                build_dataset(size, 1)
        User.objects.create_user(username="existing")
        with self.assertRaisesMessage(ValueError, "empty disposable"):
            build_dataset(10, 1)

    def test_memory_access_denied_preserves_rss(self):
        try:
            import psutil
        except ImportError:
            self.skipTest("psutil is optional")
        with patch.object(psutil, "Process") as process:
            process.return_value.memory_info.return_value.rss = 123
            process.return_value.memory_full_info.side_effect = psutil.AccessDenied()
            self.assertEqual(harness.memory(), {"rss": 123, "uss": None, "pss": None})
