"""History cards can show the tracking dates as media card properties."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from app import history_cache
from app.history_cache_serialization import (
    _deserialize_history_entry,
    _serialize_history_entry,
)
from app.models import Game, Item, MediaTypes, Movie, Sources, Status
from users.card_metadata import card_lines, parse_card_metadata


class HistoryCardDateTests(TestCase):
    """The entry carries created_at, start_date and end_date for card_lines."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="history-dates",
            password="12345",
            date_format="iso_8601",
        )
        lines = [
            {"fields": ["date_added", "start_date", "end_date"], "display": "dormant"}
        ]
        cls.user.card_metadata = parse_card_metadata(
            {
                "types": {
                    "movie": {"lines": lines},
                    "game": {"lines": lines},
                }
            }
        )
        cls.user.save()
        cls.start = timezone.now() - timedelta(days=9)
        cls.end = timezone.now() - timedelta(days=2)
        movie_item = Item.objects.create(
            media_id="dates-movie",
            source=Sources.MANUAL.value,
            media_type=MediaTypes.MOVIE.value,
            title="Dated Movie",
        )
        cls.movie = Movie.objects.create(
            item=movie_item,
            user=cls.user,
            status=Status.COMPLETED.value,
            progress=1,
            start_date=cls.start,
            end_date=cls.end,
        )
        game_item = Item.objects.create(
            media_id="dates-game",
            source=Sources.MANUAL.value,
            media_type=MediaTypes.GAME.value,
            title="Dated Game",
        )
        cls.game = Game.objects.create(
            item=game_item,
            user=cls.user,
            status=Status.COMPLETED.value,
            progress=120,
            start_date=cls.start,
            end_date=cls.end,
        )

    def setUp(self):
        cache.clear()

    def _entries(self, media_type):
        days = history_cache.build_history_days(self.user)
        return [
            entry
            for day in days
            for entry in day["entries"]
            if entry["media_type"] == media_type
        ]

    def _expected(self, record):
        local = timezone.localtime
        return " · ".join(
            local(value).strftime("%Y-%m-%d")
            for value in (record.created_at, record.start_date, record.end_date)
        )

    def test_movie_and_game_history_cards_show_the_dates(self):
        """A single-record History entry feeds every date property."""
        for media_type, record in (
            (MediaTypes.MOVIE.value, self.movie),
            (MediaTypes.GAME.value, self.game),
        ):
            entry = self._entries(media_type)[0]
            lines = card_lines(self.user, media_type, entry["item"], entry)
            self.assertEqual([line["text"] for line in lines], [self._expected(record)])

    def test_dates_survive_the_history_cache(self):
        """The cached copy of an entry keeps its dates as aware datetimes."""
        entry = self._entries(MediaTypes.MOVIE.value)[0]
        cached = _deserialize_history_entry(_serialize_history_entry(entry))
        for key in ("created_at", "start_date", "end_date"):
            self.assertEqual(cached[key], entry[key])
            self.assertTrue(timezone.is_aware(cached[key]))
