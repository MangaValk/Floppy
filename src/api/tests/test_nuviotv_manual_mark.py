"""What Floppy does when someone marks a title watched by hand (#1671).

NuvioTV's Mark Watched button is not playback: there is no position, no
duration and no start. The client sends the same `stop` it sends for a finished
film, plus `manual: true`. The difference Floppy owes it is that marking
something already watched changes nothing, so a retry, a double tap or a second
device cannot grow a user's history.
"""

import datetime
from http import HTTPStatus as HTTP  # noqa: N814
from unittest.mock import patch

from django.utils import timezone

from app.models import Episode, Movie, MoviePlay, Status
from integrations.models import IntegrationToken
from integrations.webhooks.generic_scrobble import GenericScrobbleProcessor

from .base import FloppyApiTestCase

SCROBBLE = "/api/v1/scrobble/"

MATRIX = {
    "title": "The Matrix",
    "image": "https://example.com/matrix.jpg",
    "max_progress": 1,
    "provider_external_ids": {},
}
FRIENDS = {
    "media_id": "1668",
    "title": "Friends",
    "image": "https://example.com/friends.jpg",
    "tvdb_id": "79175",
    "provider_external_ids": {"tmdb_id": "1668", "tvdb_id": "79175"},
    "season/1": {
        "season_number": 1,
        "image": "https://example.com/friends-s1.jpg",
        "episodes": [
            {
                "episode_number": 1,
                "runtime": 22,
                "air_date": None,
                "still_path": None,
                "name": "The Pilot",
                "overview": "",
            },
            {"episode_number": 2},
        ],
    },
}

MOVIE_MARK = {
    "action": "stop",
    "media_type": "movie",
    "ids": {"imdb": "tt0133093", "tmdb": "603"},
    "title": "The Matrix",
    "completed": True,
    "manual": True,
}
MOVIE_PLAYED = {**MOVIE_MARK, "manual": False}
EPISODE_MARK = {
    "action": "stop",
    "media_type": "episode",
    "ids": {"tmdb": "1668"},
    "series_title": "Friends",
    "title": "The Pilot",
    "season_number": 1,
    "episode_number": 1,
    "completed": True,
    "manual": True,
}
EPISODE_PLAYED = {**EPISODE_MARK, "manual": False}

LONG_AGO = datetime.datetime(2020, 1, 1, 20, tzinfo=datetime.UTC)


@patch("app.live_playback._attach_resolved_image")
@patch("app.providers.tmdb.movie", return_value=MATRIX)
@patch.object(
    GenericScrobbleProcessor,
    "_find_tv_media_id",
    return_value=("1668", None, None),
)
@patch("app.providers.tmdb.get_tvdb_episode_image_map", return_value={})
@patch("app.providers.tmdb.tv_with_seasons", return_value=FRIENDS)
class ManualMarkTests(FloppyApiTestCase):
    """Marking watched by hand is idempotent; playing something is not."""

    def setUp(self):
        """Mint the default-preset token a user pastes into NuvioTV."""
        super().setUp()
        self.user1.anime_enabled = False
        self.user1.save(update_fields=["anime_enabled"])
        _, secret = IntegrationToken.generate(user=self.user1, name="NuvioTV")
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {secret}"}

    def _send(self, payload, event_id=None):
        body = {**payload, **({"client_event_id": event_id} if event_id else {})}
        return self.client.post(SCROBBLE, body, format="json", **self.headers)

    def _movies(self):
        return Movie.objects.filter(user=self.user1, item__media_id="603")

    def _episodes(self):
        return Episode.objects.filter(
            item__media_id="1668",
            item__season_number=1,
            item__episode_number=1,
            related_season__user=self.user1,
        )

    def _age(self, queryset):
        queryset.update(end_date=LONG_AGO)

    def test_marking_an_unseen_movie_completes_it_once(self, *_mocks):
        """No playback needed: the title is found, created and completed."""
        response = self._send(MOVIE_MARK)

        self.assertEqual(response.status_code, HTTP.OK)
        movie = self._movies().get()
        self.assertEqual(movie.status, Status.COMPLETED.value)
        self.assertIsNotNone(movie.end_date)

    def test_marking_a_tracked_movie_completes_the_row_it_has(self, *_mocks):
        """A Planning entry becomes Completed instead of gaining a second row."""
        self._send({**MOVIE_PLAYED, "completed": False})
        self._movies().update(status=Status.PLANNING.value)

        self._send(MOVIE_MARK)

        movie = self._movies().get()
        self.assertEqual(movie.status, Status.COMPLETED.value)

    def test_marking_a_watched_movie_again_adds_no_rewatch(self, *_mocks):
        """The user watched it years ago; a tap today is agreement, not a play."""
        self._send(MOVIE_MARK, "first")
        self._age(self._movies())

        response = self._send(MOVIE_MARK, "second")

        self.assertEqual(response.status_code, HTTP.OK)
        movie = self._movies().get()
        self.assertEqual(movie.end_date, LONG_AGO)

    def test_marking_does_not_disturb_recorded_plays(self, *_mocks):
        """History kept from an unmark or an import stays exactly as it was."""
        self._send(MOVIE_MARK, "first")
        movie = self._movies().get()
        movie.watch(LONG_AGO)
        before = MoviePlay.objects.filter(movie=movie).count()
        self.assertGreater(before, 0)

        self._send(MOVIE_MARK, "again")

        self.assertEqual(self._movies().count(), 1)
        self.assertEqual(MoviePlay.objects.filter(movie=movie).count(), before)

    def test_a_retried_mark_is_the_same_result(self, *_mocks):
        """The same client_event_id replays the first answer."""
        first = self._send(MOVIE_MARK, "retry-me")
        again = self._send(MOVIE_MARK, "retry-me")

        self.assertEqual(first.status_code, HTTP.OK)
        self.assertEqual(again.status_code, HTTP.OK)
        self.assertEqual(self._movies().count(), 1)

    def test_playing_a_watched_movie_again_is_still_a_rewatch(self, *_mocks):
        """Only a manual mark is treated as agreement; real plays still count."""
        self._send(MOVIE_PLAYED, "first")
        self._age(self._movies())

        self._send(MOVIE_PLAYED, "second")

        self.assertEqual(self._movies().count(), 2)

    def test_marking_an_unwatched_episode_records_one_watch(self, *_mocks):
        """Episodes are marked the same way, by season and episode number."""
        response = self._send(EPISODE_MARK)

        self.assertEqual(response.status_code, HTTP.OK)
        self.assertEqual(self._episodes().count(), 1)

    def test_marking_a_watched_episode_again_adds_no_watch(self, *_mocks):
        """An old watch is not duplicated by a tap days later."""
        self._send(EPISODE_MARK, "first")
        self._age(self._episodes())

        self._send(EPISODE_MARK, "second")

        self.assertEqual(self._episodes().count(), 1)
        self.assertEqual(self._episodes().get().end_date, LONG_AGO)

    def test_playing_a_watched_episode_again_is_still_a_rewatch(self, *_mocks):
        """The guard is for manual marks only."""
        self._send(EPISODE_PLAYED, "first")
        self._age(self._episodes())

        self._send(EPISODE_PLAYED, "second")

        self.assertEqual(self._episodes().count(), 2)

    def test_manual_must_be_a_boolean(self, *_mocks):
        """A string would silently read as 'not manual', so it is refused."""
        response = self._send({**MOVIE_MARK, "manual": "yes"})

        self.assertEqual(response.status_code, HTTP.BAD_REQUEST)
        self.assertFalse(self._movies().exists())

    def test_a_manual_flag_on_start_is_ignored(self, *_mocks):
        """Only a stop writes; a start stays a Now Playing card."""
        response = self._send({**MOVIE_MARK, "action": "start"})

        self.assertEqual(response.status_code, HTTP.OK)
        self.assertFalse(self._movies().exists())

    def test_a_manual_mark_can_carry_the_time_the_user_means(self, *_mocks):
        """`played_at` still sets the watch date when the client has one."""
        played_at = timezone.now() - datetime.timedelta(days=3)

        response = self._send({**MOVIE_MARK, "played_at": played_at.isoformat()})

        self.assertEqual(response.status_code, HTTP.OK)
        self.assertEqual(
            self._movies().get().end_date.date(),
            played_at.date(),
        )
