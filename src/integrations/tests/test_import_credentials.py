"""Background jobs must see the user's personal provider keys (#1488).

A Celery task runs no middleware, so the importer only resolves a personal
Client ID/API key when the task itself publishes the user.
"""

from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from app.models import Game
from app.providers import credentials
from integrations.models import LastFMAccount
from integrations.tasks import _lastfm
from integrations.tasks._media_imports import import_media, import_steam


@override_settings(SIMKL_ID="", SIMKL_SECRET="", LASTFM_API_KEY="")
class PersonalCredentialsInBackgroundJobsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="personal-keys")
        credentials.set_user(
            "simkl",
            self.user,
            {"client_id": "personal-id", "client_secret": "personal-secret"},
        )
        credentials.set_user("lastfm", self.user, {"api_key": "personal-lastfm"})

    def test_import_media_resolves_the_users_personal_keys(self):
        seen = {}

        def importer(identifier, user, mode, **kwargs):
            seen["client_id"] = credentials.get("simkl", "client_id")
            return {"created": 0, "updated": 0, "skipped": 0}, ""

        with (
            patch("app.mixins.disable_fetch_releases"),
            patch("integrations.tasks._media_imports.import_progress.tracking"),
        ):
            import_media(importer, None, self.user.id, "new")

        self.assertEqual(seen["client_id"], "personal-id")
        # The scope ends with the task: nothing leaks into the next one.
        self.assertEqual(credentials.get("simkl", "client_id"), "")

    @override_settings(IGDB_ID="", IGDB_SECRET="", STEAM_API_KEY="")
    def test_steam_import_uses_personal_igdb_credentials(self):
        """Steam matching must use personal Twitch credentials in Celery (#1511)."""
        cache.clear()
        self.addCleanup(cache.clear)
        credentials.set_user(
            "igdb",
            self.user,
            {"client_id": "personal-igdb", "client_secret": "personal-igdb-secret"},
        )
        credentials.set_user("steam", self.user, {"api_key": "personal-steam"})

        with (
            patch("app.providers.services.api_request") as request,
            patch("app.providers.services.get_media_metadata") as metadata,
        ):
            request.side_effect = [
                {"response": {"games": [{"appid": 730, "name": "Counter-Strike 2"}]}},
                {"access_token": "personal-token", "expires_in": 3600},
                [{"game": 123}],
            ]
            metadata.return_value = {"title": "Counter-Strike 2", "image": ""}

            import_steam.run("76561198000000000", self.user.id, "new")

        steam_request, token_request, igdb_request = request.call_args_list
        self.assertEqual(steam_request.kwargs["params"]["key"], "personal-steam")
        self.assertEqual(
            token_request.kwargs["params"],
            {
                "client_id": "personal-igdb",
                "client_secret": "personal-igdb-secret",
                "grant_type": "client_credentials",
            },
        )
        self.assertEqual(
            igdb_request.kwargs["headers"],
            {"Client-ID": "personal-igdb", "Authorization": "Bearer personal-token"},
        )
        self.assertTrue(Game.objects.filter(user=self.user, item__media_id="123").exists())
        self.assertEqual(credentials.get("igdb", "client_id"), "")
        self.assertEqual(credentials.get("igdb", "client_secret"), "")

    def test_lastfm_poll_resolves_the_users_personal_key(self):
        LastFMAccount.objects.create(user=self.user, lastfm_username="listener")
        seen = {}

        def sync(account):
            seen["api_key"] = credentials.get("lastfm", "api_key")
            return {"status": "success", "message": "ok"}

        with (
            patch.object(LastFMAccount, "is_connected", True),
            patch.object(_lastfm, "_run_incremental_lastfm_sync", sync),
        ):
            _lastfm.poll_lastfm_for_user(self.user.id)

        self.assertEqual(seen["api_key"], "personal-lastfm")

    def test_lastfm_history_import_resolves_the_users_personal_key(self):
        seen = {}

        def chunk(user_id, reset, import_run_id):
            seen["api_key"] = credentials.get("lastfm", "api_key")
            return {}

        with patch.object(_lastfm, "_import_lastfm_history_chunk", Mock(side_effect=chunk)):
            _lastfm.import_lastfm_history(self.user.id)

        self.assertEqual(seen["api_key"], "personal-lastfm")
