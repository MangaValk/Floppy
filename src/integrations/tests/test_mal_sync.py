"""Tests for syncing watch status from Floppy to MyAnimeList."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from app.models import (
    Anime,
    Item,
    Manga,
    MediaTypes,
    Sources,
    Status,
)
from app.providers.services import ProviderAPIError
from integrations import mal_sync, tasks
from integrations.imports.helpers import decrypt
from integrations.models import MALAccount


def _make_user(username="test", password="12345"):  # noqa: S107 (test fixture)
    """Create a user for tests."""
    return get_user_model().objects.create_user(username=username, password=password)


def make_mal_account(
    user,
    *,
    sync_enabled=True,
    per_item_sync_enabled=True,
    connection_broken=False,
    expired=False,
):
    """Create a MALAccount for a user with encrypted placeholder tokens."""
    expires_at = timezone.now() + (
        timedelta(hours=-1) if expired else timedelta(hours=1)
    )
    return MALAccount.objects.create(
        user=user,
        mal_username=f"{user.username}_mal",
        access_token=mal_sync.encrypt("old-access-token"),
        refresh_token=mal_sync.encrypt("old-refresh-token"),
        token_expires_at=expires_at,
        sync_enabled=sync_enabled,
        per_item_sync_enabled=per_item_sync_enabled,
        connection_broken=connection_broken,
    )


def _http_error(response):
    """Build a requests.exceptions.HTTPError carrying the given fake response."""
    return requests.exceptions.HTTPError(response=response)


@patch("integrations.mal_sync.client_id", return_value="test_client_id")
@patch("integrations.mal_sync.client_secret", return_value="test_client_secret")
class MALSyncModelHooks(TestCase):
    """Test that Anime/Manga.save() queues MyAnimeList sync at the right times."""

    def setUp(self):
        """Create a user and MAL-backed/non-MAL-backed items."""
        self.user = _make_user()
        self.mal_anime_item = Item.objects.create(
            media_id="1",
            source=Sources.MAL.value,
            media_type=MediaTypes.ANIME.value,
            title="Test Anime",
        )
        self.mal_manga_item = Item.objects.create(
            media_id="2",
            source=Sources.MAL.value,
            media_type=MediaTypes.MANGA.value,
            title="Test Manga",
        )
        self.tmdb_anime_item = Item.objects.create(
            media_id="3",
            source=Sources.TMDB.value,
            media_type=MediaTypes.ANIME.value,
            title="Test TMDB-sourced Anime",
        )

    @patch("integrations.tasks.sync_mal_status.delay")
    def test_status_change_queues_anime_sync(self, mock_delay, *_mocks):
        """Changing status on a MAL-backed anime queues a sync."""
        anime = Anime.objects.create(
            user=self.user,
            item=self.mal_anime_item,
            status=Status.PLANNING.value,
        )
        mock_delay.reset_mock()

        anime.status = Status.PAUSED.value
        anime.save()

        mock_delay.assert_called_once_with(media_type="anime", media_id=anime.pk)

    @patch("integrations.tasks.sync_mal_status.delay")
    def test_progress_change_queues_sync(self, mock_delay, *_mocks):
        """Changing progress on a MAL-backed anime queues a sync."""
        anime = Anime.objects.create(
            user=self.user,
            item=self.mal_anime_item,
            status=Status.PAUSED.value,
            progress=1,
        )
        mock_delay.reset_mock()

        anime.progress = 2
        anime.save()

        mock_delay.assert_called_once_with(media_type="anime", media_id=anime.pk)

    @patch("integrations.tasks.sync_mal_status.delay")
    def test_score_change_queues_sync(self, mock_delay, *_mocks):
        """Changing score on a MAL-backed manga queues a sync."""
        manga = Manga.objects.create(
            user=self.user,
            item=self.mal_manga_item,
            status=Status.PAUSED.value,
        )
        mock_delay.reset_mock()

        manga.score = Decimal("8.0")
        manga.save()

        mock_delay.assert_called_once_with(media_type="manga", media_id=manga.pk)

    @patch("integrations.tasks.sync_mal_status.delay")
    def test_unrelated_field_change_does_not_queue(self, mock_delay, *_mocks):
        """Editing notes only, with no status/progress/score change, doesn't sync."""
        anime = Anime.objects.create(
            user=self.user,
            item=self.mal_anime_item,
            status=Status.PAUSED.value,
        )
        mock_delay.reset_mock()

        anime.notes = "spoiler-free thoughts"
        anime.save()

        mock_delay.assert_not_called()

    @patch("integrations.tasks.sync_mal_status.delay")
    def test_tmdb_backed_anime_never_queues(self, mock_delay, *_mocks):
        """Anime sourced from TMDB (not MAL) never queues a MAL sync."""
        anime = Anime.objects.create(
            user=self.user,
            item=self.tmdb_anime_item,
            status=Status.PLANNING.value,
        )
        mock_delay.reset_mock()

        anime.status = Status.PAUSED.value
        anime.save()

        mock_delay.assert_not_called()

    @patch("integrations.tasks.sync_mal_status.delay")
    def test_creating_with_initial_status_queues_sync(self, mock_delay, *_mocks):
        """Adding a new MAL-backed entry queues a sync too, not just later edits."""
        anime = Anime.objects.create(
            user=self.user,
            item=self.mal_anime_item,
            status=Status.PAUSED.value,
        )

        mock_delay.assert_called_once_with(media_type="anime", media_id=anime.pk)

    @patch("integrations.tasks.sync_mal_status.delay")
    def test_completion_still_queues_sync_alongside_auto_migration(
        self,
        mock_delay,
        *_mocks,
    ):
        """Completing a flat MAL anime queues a sync even though it also
        triggers Floppy's own auto-migration to episode tracking.
        """
        anime = Anime.objects.create(
            user=self.user,
            item=self.mal_anime_item,
            status=Status.IN_PROGRESS.value,
            progress=1,
        )
        mock_delay.reset_mock()

        anime.status = Status.COMPLETED.value
        anime.save()

        mock_delay.assert_called_once_with(media_type="anime", media_id=anime.pk)


@override_settings(URLS=["https://floppy.example.com"])
@patch("integrations.mal_sync.client_id", return_value="test_client_id")
@patch("integrations.mal_sync.client_secret", return_value="test_client_secret")
class MALOAuthConnectView(TestCase):
    """Test the view that starts the MyAnimeList OAuth flow."""

    def setUp(self):
        """Create and log in a user."""
        self.user = _make_user()
        self.client.force_login(self.user)

    def test_connect_without_configuration_shows_error(self, mock_secret, mock_id):
        """Without both credentials configured, connecting fails clearly."""
        mock_secret.return_value = ""
        response = self.client.post(reverse("mal_oauth"), follow=True)

        self.assertRedirects(response, reverse("import_data"))
        self.assertContains(response, "isn&#x27;t configured")

    def test_connect_redirects_to_mal_with_pkce(self, *_mocks):
        """Connecting redirects to MAL's authorize endpoint with PKCE params."""
        response = self.client.post(reverse("mal_oauth"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(mal_sync.AUTHORIZE_URL))
        self.assertIn("client_id=test_client_id", response.url)
        self.assertIn("code_challenge_method=plain", response.url)

        state_entries = [v for v in self.client.session.values() if isinstance(v, dict)]
        self.assertEqual(len(state_entries), 1)
        self.assertIn("code_verifier", state_entries[0])

    @patch("app.helpers.supports_oauth_redirect", return_value=False)
    def test_connect_blocked_on_http_only_instance(self, *_mocks):
        """No device-code fallback exists for MAL, so HTTP-only instances are blocked."""
        response = self.client.post(reverse("mal_oauth"), follow=True)

        self.assertRedirects(response, reverse("import_data"))
        self.assertContains(response, "HTTPS-accessible")


@override_settings(URLS=["https://floppy.example.com"])
@patch("integrations.mal_sync.client_id", return_value="test_client_id")
@patch("integrations.mal_sync.client_secret", return_value="test_client_secret")
class MALOAuthCallbackView(TestCase):
    """Test the view that handles MyAnimeList's OAuth callback."""

    def setUp(self):
        """Create and log in a user."""
        self.user = _make_user()
        self.client.force_login(self.user)

    def _seed_state(self):
        response = self.client.post(reverse("mal_oauth"))
        return response.url.split("state=")[1].split("&")[0]

    def test_callback_invalid_state_shows_error(self, *_mocks):
        """A missing/unrecognized state token is rejected."""
        response = self.client.get(
            reverse("mal_callback"),
            {"state": "unknown", "code": "somecode"},
            follow=True,
        )

        self.assertRedirects(response, reverse("import_data"))
        self.assertFalse(MALAccount.objects.filter(user=self.user).exists())

    def test_callback_missing_code_shows_error(self, *_mocks):
        """A callback with no code param is rejected."""
        state_token = self._seed_state()

        response = self.client.get(
            reverse("mal_callback"),
            {"state": state_token},
            follow=True,
        )

        self.assertRedirects(response, reverse("import_data"))
        self.assertFalse(MALAccount.objects.filter(user=self.user).exists())

    @patch("requests.Session.get")
    @patch("requests.Session.post")
    def test_callback_success_creates_account(self, mock_post, mock_get, *_mocks):
        """A valid callback exchanges the code and stores the connection."""
        state_token = self._seed_state()

        token_response = MagicMock()
        token_response.json.return_value = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
        }
        mock_post.return_value = token_response
        user_response = MagicMock()
        user_response.json.return_value = {"name": "MyMalUser"}
        mock_get.return_value = user_response

        response = self.client.get(
            reverse("mal_callback"),
            {"state": state_token, "code": "authcode"},
            follow=True,
        )

        self.assertRedirects(response, reverse("import_data"))
        account = MALAccount.objects.get(user=self.user)
        self.assertEqual(account.mal_username, "MyMalUser")
        self.assertEqual(decrypt(account.access_token), "new-access-token")
        self.assertTrue(account.sync_enabled)
        self.assertFalse(account.connection_broken)
        self.assertNotIn(state_token, self.client.session)
        self.assertEqual(mock_post.call_args.kwargs["data"]["code"], "authcode")

    @patch("requests.Session.post")
    def test_callback_mal_error_shows_message(self, mock_post, *_mocks):
        """If MAL rejects the code exchange, no account is created."""
        state_token = self._seed_state()
        error_response = MagicMock(status_code=400, text="invalid_grant")
        error_response.raise_for_status.side_effect = _http_error(error_response)
        mock_post.return_value = error_response

        response = self.client.get(
            reverse("mal_callback"),
            {"state": state_token, "code": "badcode"},
            follow=True,
        )

        self.assertRedirects(response, reverse("import_data"))
        self.assertFalse(MALAccount.objects.filter(user=self.user).exists())


class MALDisconnectToggleViews(TestCase):
    """Test disconnecting and pausing/resuming sync."""

    def setUp(self):
        """Create and log in a user with a connected MAL account."""
        self.user = _make_user()
        self.client.force_login(self.user)
        self.account = make_mal_account(self.user)

    def test_disconnect_removes_account(self):
        """Disconnecting deletes the MALAccount row."""
        self.client.post(reverse("mal_disconnect"))
        self.assertFalse(MALAccount.objects.filter(user=self.user).exists())

    def test_toggle_off_then_on(self):
        """The sync toggle can turn syncing off and back on."""
        self.client.post(reverse("mal_toggle"), {"enabled": "false"})
        self.account.refresh_from_db()
        self.assertFalse(self.account.sync_enabled)

        self.client.post(reverse("mal_toggle"), {"enabled": "true"})
        self.account.refresh_from_db()
        self.assertTrue(self.account.sync_enabled)

    def test_toggle_without_account_shows_error(self):
        """Toggling with no connected account shows an error, not a crash."""
        self.account.delete()
        response = self.client.post(
            reverse("mal_toggle"),
            {"enabled": "true"},
            follow=True,
        )
        self.assertContains(response, "Connect a MyAnimeList account")

    def test_per_item_toggle_off_then_on(self):
        """The per-item toggle can turn per-item pushes off and back on."""
        self.client.post(reverse("mal_per_item_sync_toggle"), {"enabled": "false"})
        self.account.refresh_from_db()
        self.assertFalse(self.account.per_item_sync_enabled)

        self.client.post(reverse("mal_per_item_sync_toggle"), {"enabled": "true"})
        self.account.refresh_from_db()
        self.assertTrue(self.account.per_item_sync_enabled)

    def test_per_item_toggle_leaves_overall_sync_enabled_alone(self):
        """The per-item toggle is independent of the overall sync_enabled flag."""
        self.client.post(reverse("mal_per_item_sync_toggle"), {"enabled": "false"})
        self.account.refresh_from_db()
        self.assertFalse(self.account.per_item_sync_enabled)
        self.assertTrue(self.account.sync_enabled)

    def test_per_item_toggle_without_account_shows_error(self):
        """Toggling with no connected account shows an error, not a crash."""
        self.account.delete()
        response = self.client.post(
            reverse("mal_per_item_sync_toggle"),
            {"enabled": "true"},
            follow=True,
        )
        self.assertContains(response, "Connect a MyAnimeList account")


@patch("integrations.mal_sync.client_id", return_value="test_client_id")
@patch("integrations.mal_sync.client_secret", return_value="test_client_secret")
class PushStatus(TestCase):
    """Test mapping Floppy fields onto MAL's my_list_status endpoint."""

    def setUp(self):
        """Create a user, a connected MAL account, and MAL-backed items."""
        self.user = _make_user()
        self.account = make_mal_account(self.user)
        self.anime_item = Item.objects.create(
            media_id="42",
            source=Sources.MAL.value,
            media_type=MediaTypes.ANIME.value,
            title="Test Anime",
        )
        self.manga_item = Item.objects.create(
            media_id="99",
            source=Sources.MAL.value,
            media_type=MediaTypes.MANGA.value,
            title="Test Manga",
        )

    @patch("requests.Session.put")
    def test_push_anime_status_and_progress(self, mock_put, *_mocks):
        """Anime pushes status + num_watched_episodes, using the anime status map."""
        mock_put.return_value = MagicMock(
            json=lambda: {"status": "on_hold", "num_episodes_watched": 5},
        )
        anime = Anime.objects.create(
            user=self.user,
            item=self.anime_item,
            status=Status.PAUSED.value,
            progress=5,
        )

        mal_sync.push_status(anime, self.account)

        self.assertIn("/anime/42/my_list_status", mock_put.call_args.kwargs["url"])
        data = mock_put.call_args.kwargs["data"]
        self.assertEqual(data["status"], "on_hold")
        self.assertEqual(data["num_watched_episodes"], 5)
        self.assertNotIn("score", data)

    @patch("requests.Session.put")
    def test_push_manga_uses_chapters_and_manga_status_map(self, mock_put, *_mocks):
        """Manga pushes num_chapters_read and maps status onto MAL's manga statuses."""
        mock_put.return_value = MagicMock(
            json=lambda: {"status": "dropped", "num_chapters_read": 64, "score": 8},
        )
        manga = Manga.objects.create(
            user=self.user,
            item=self.manga_item,
            status=Status.DROPPED.value,
            progress=64,
            score=Decimal("7.8"),
        )

        mal_sync.push_status(manga, self.account)

        data = mock_put.call_args.kwargs["data"]
        self.assertEqual(data["status"], "dropped")
        self.assertEqual(data["num_chapters_read"], 64)
        self.assertEqual(data["score"], 8)

    @patch("requests.Session.put")
    @patch("requests.Session.post")
    def test_push_refreshes_expired_token_first(self, mock_post, mock_put, *_mocks):
        """An expired access token is refreshed before pushing the update."""
        self.account.token_expires_at = timezone.now() - timedelta(minutes=5)
        self.account.save()

        refresh_response = MagicMock()
        refresh_response.json.return_value = {
            "access_token": "refreshed-access-token",
            "refresh_token": "refreshed-refresh-token",
            "expires_in": 3600,
        }
        mock_post.return_value = refresh_response
        mock_put.return_value = MagicMock(
            json=lambda: {"status": "on_hold", "num_episodes_watched": 0},
        )

        anime = Anime.objects.create(
            user=self.user,
            item=self.anime_item,
            status=Status.PAUSED.value,
        )

        mal_sync.push_status(anime, self.account)

        self.account.refresh_from_db()
        self.assertEqual(decrypt(self.account.access_token), "refreshed-access-token")
        self.assertEqual(
            mock_put.call_args.kwargs["headers"]["Authorization"],
            "Bearer refreshed-access-token",
        )

    @patch("requests.Session.post")
    def test_refresh_failure_raises_auth_error(self, mock_post, *_mocks):
        """A revoked refresh token surfaces as a clean MALAuthError."""
        self.account.token_expires_at = timezone.now() - timedelta(minutes=5)
        self.account.save()
        error_response = MagicMock(status_code=401, text="invalid_grant")
        error_response.raise_for_status.side_effect = _http_error(error_response)
        mock_post.return_value = error_response

        with self.assertRaises(mal_sync.MALAuthError):
            mal_sync.get_valid_access_token(self.account)


class PreviewFullSync(TestCase):
    """Test the read-only diff used before a full MAL sync."""

    def setUp(self):
        self.user = _make_user()
        self.account = make_mal_account(self.user)
        with patch("integrations.tasks.sync_mal_status.delay"):
            self.anime = Anime.objects.create(
                user=self.user,
                item=Item.objects.create(
                    media_id="42",
                    source=Sources.MAL.value,
                    media_type=MediaTypes.ANIME.value,
                    title="Changed Anime",
                ),
                # Dropped, not Paused/Planning, so this stays covered by the
                # default sync filters (see MALSyncFiltersTests below).
                status=Status.DROPPED.value,
                progress=5,
                score=Decimal("7.6"),
            )
            self.manga = Manga.objects.create(
                user=self.user,
                item=Item.objects.create(
                    media_id="99",
                    source=Sources.MAL.value,
                    media_type=MediaTypes.MANGA.value,
                    title="Unchanged Manga",
                ),
                status=Status.COMPLETED.value,
                progress=0,
            )

    @patch("integrations.mal_sync.services.api_request")
    def test_returns_only_fields_that_would_change(self, mock_request):
        mock_request.side_effect = [
            {
                "data": [
                    {
                        "node": {"id": 42},
                        "list_status": {
                            "status": "watching",
                            "num_episodes_watched": 5,
                            "score": 7,
                        },
                    }
                ],
                "paging": {},
            },
            {
                "data": [
                    {
                        "node": {"id": 99},
                        "list_status": {
                            "status": "completed",
                            "num_chapters_read": 0,
                            "score": 0,
                        },
                    }
                ],
                "paging": {},
            },
        ]

        preview = mal_sync.preview_full_sync(self.user, self.account)

        self.assertEqual(
            preview,
            [
                {
                    "title": "Changed Anime",
                    "media_type": "Anime",
                    "mal_id": "42",
                    "not_on_list": False,
                    "changes": [
                        {"field": "Status", "from": "watching", "to": "dropped"},
                        {"field": "Score", "from": 7, "to": 8},
                    ],
                }
            ],
        )

    @patch("integrations.mal_sync.services.api_request")
    def test_marks_entries_missing_from_mal(self, mock_request):
        mock_request.side_effect = [
            {"data": [], "paging": {}},
            {"data": [], "paging": {}},
        ]

        preview = mal_sync.preview_full_sync(self.user, self.account)

        self.assertEqual(len(preview), 2)
        self.assertTrue(all(entry["not_on_list"] for entry in preview))


class SyncMALStatusTask(TestCase):
    """Test the Celery task that drives a single push to MyAnimeList."""

    def setUp(self):
        """Create a user, item and anime entry to sync."""
        self.user = _make_user()
        self.item = Item.objects.create(
            media_id="1",
            source=Sources.MAL.value,
            media_type=MediaTypes.ANIME.value,
            title="Test Anime",
        )
        with patch("integrations.tasks.sync_mal_status.delay"):
            self.anime = Anime.objects.create(
                user=self.user,
                item=self.item,
                status=Status.PAUSED.value,
            )

    def test_noop_when_media_deleted(self):
        """A media row deleted before the task runs is a silent no-op."""
        pk = self.anime.pk
        self.anime.delete()
        tasks.sync_mal_status(media_type="anime", media_id=pk)  # should not raise

    def test_noop_when_no_mal_account(self):
        """No MAL connection at all is a silent no-op."""
        with patch("integrations.mal_sync.push_status") as mock_push:
            tasks.sync_mal_status(media_type="anime", media_id=self.anime.pk)
        mock_push.assert_not_called()

    def test_noop_when_sync_disabled_or_broken(self):
        """A paused or broken connection is a silent no-op."""
        make_mal_account(self.user, sync_enabled=False)
        with patch("integrations.mal_sync.push_status") as mock_push:
            tasks.sync_mal_status(media_type="anime", media_id=self.anime.pk)
        mock_push.assert_not_called()

    def test_noop_when_per_item_sync_disabled(self):
        """Turning off per-item sync stops the per-save push only."""
        account = make_mal_account(self.user)
        account.per_item_sync_enabled = False
        account.save(update_fields=["per_item_sync_enabled"])

        with patch("integrations.mal_sync.push_status") as mock_push:
            tasks.sync_mal_status(media_type="anime", media_id=self.anime.pk)

        mock_push.assert_not_called()

    def test_calls_push_status_when_connected(self):
        """A healthy, enabled connection gets pushed to."""
        account = make_mal_account(self.user)
        with patch("integrations.mal_sync.push_status") as mock_push:
            tasks.sync_mal_status(media_type="anime", media_id=self.anime.pk)
        mock_push.assert_called_once_with(self.anime, account)

    def test_noop_when_media_has_no_status(self):
        """Statusless imported media has no MAL list status to push."""
        make_mal_account(self.user)
        Anime.objects.filter(pk=self.anime.pk).update(status=None)

        with patch("integrations.mal_sync.push_status") as mock_push:
            tasks.sync_mal_status(media_type="anime", media_id=self.anime.pk)

        mock_push.assert_not_called()

    def test_finds_anime_migrated_to_episode_tracking(self):
        """all_objects (not the default manager) still finds a migrated row."""
        make_mal_account(self.user)
        Anime.objects.filter(pk=self.anime.pk).update(migrated_to_item_id=None)
        # Simulate migration by pointing at a placeholder item id, matching how
        # the default ActiveAnimeManager excludes rows with migrated_to_item set.
        other_item = Item.objects.create(
            media_id="999",
            source=Sources.TMDB.value,
            media_type=MediaTypes.TV.value,
            title="Migrated placeholder",
        )
        Anime.objects.filter(pk=self.anime.pk).update(migrated_to_item=other_item)
        self.assertFalse(Anime.objects.filter(pk=self.anime.pk).exists())
        self.assertTrue(Anime.all_objects.filter(pk=self.anime.pk).exists())

        with patch("integrations.mal_sync.push_status") as mock_push:
            tasks.sync_mal_status(media_type="anime", media_id=self.anime.pk)
        mock_push.assert_called_once()

    def test_not_found_from_mal_is_logged_not_raised(self):
        """A 404 from MAL (e.g. a deleted MAL entry) doesn't raise or retry."""
        make_mal_account(self.user)
        error = ProviderAPIError("MAL", MagicMock(response=MagicMock(status_code=404)))
        with patch("integrations.mal_sync.push_status", side_effect=error):
            tasks.sync_mal_status(
                media_type="anime", media_id=self.anime.pk
            )  # no raise

    def test_other_provider_errors_propagate_for_retry(self):
        """A transient (e.g. 5xx) error is re-raised so Celery can retry it."""
        make_mal_account(self.user)
        error = ProviderAPIError("MAL", MagicMock(response=MagicMock(status_code=503)))
        with (
            patch("integrations.mal_sync.push_status", side_effect=error),
            self.assertRaises(ProviderAPIError),
        ):
            tasks.sync_mal_status(media_type="anime", media_id=self.anime.pk)

    def test_auth_error_breaks_connection(self):
        """An expired/revoked connection turns sync off and records why."""
        account = make_mal_account(self.user)
        with patch(
            "integrations.mal_sync.push_status",
            side_effect=mal_sync.MALAuthError("expired"),
        ):
            tasks.sync_mal_status(media_type="anime", media_id=self.anime.pk)

        account.refresh_from_db()
        self.assertTrue(account.connection_broken)
        self.assertFalse(account.sync_enabled)
        self.assertIn("expired", account.last_error_message)


class BulkSyncMALStatusTask(TestCase):
    """Test the one-off "Sync All Now" background task."""

    def setUp(self):
        """Create a user with a mix of MAL-backed and non-MAL-backed entries."""
        self.user = _make_user()
        with patch("integrations.tasks.sync_mal_status.delay"):
            self.anime = Anime.objects.create(
                user=self.user,
                item=Item.objects.create(
                    media_id="1",
                    source=Sources.MAL.value,
                    media_type=MediaTypes.ANIME.value,
                    title="Anime One",
                ),
                # Covered by the default sync filters (watched); Planning
                # and Paused are excluded by default (MALSyncFiltersTests).
                status=Status.IN_PROGRESS.value,
            )
            self.manga = Manga.objects.create(
                user=self.user,
                item=Item.objects.create(
                    media_id="2",
                    source=Sources.MAL.value,
                    media_type=MediaTypes.MANGA.value,
                    title="Manga One",
                ),
                status=Status.IN_PROGRESS.value,
            )
            self.tmdb_anime = Anime.objects.create(
                user=self.user,
                item=Item.objects.create(
                    media_id="3",
                    source=Sources.TMDB.value,
                    media_type=MediaTypes.ANIME.value,
                    title="TMDB-sourced Anime",
                ),
                status=Status.IN_PROGRESS.value,
            )

    def test_noop_when_no_account(self):
        """No connection at all is a silent no-op."""
        with patch("integrations.mal_sync.push_status") as mock_push:
            tasks.bulk_sync_mal_status(user_id=self.user.pk)
        mock_push.assert_not_called()

    def test_queued_sync_fails_cleanly_when_sync_was_disabled(self):
        account = make_mal_account(self.user, sync_enabled=False)
        account.full_sync_status = "queued"
        account.save(update_fields=["full_sync_status"])

        with patch("integrations.mal_sync.push_status") as mock_push:
            tasks.bulk_sync_mal_status(user_id=self.user.pk)

        mock_push.assert_not_called()
        account.refresh_from_db()
        self.assertEqual(account.full_sync_status, "failed")
        self.assertIn("disabled", account.full_sync_results[0]["reason"])

    def test_pushes_only_mal_backed_entries(self):
        """Every MAL-sourced anime/manga is pushed; the TMDB one is skipped."""
        make_mal_account(self.user)
        with patch("integrations.mal_sync.push_status") as mock_push:
            tasks.bulk_sync_mal_status(user_id=self.user.pk)

        pushed = {call.args[0] for call in mock_push.call_args_list}
        self.assertEqual(pushed, {self.anime, self.manga})
        account = MALAccount.objects.get(user=self.user)
        self.assertEqual(account.full_sync_status, "completed")
        self.assertEqual(account.full_sync_total, 2)
        self.assertEqual(account.full_sync_processed, 2)
        self.assertEqual(account.full_sync_succeeded, 2)
        self.assertEqual(account.full_sync_failed, 0)
        self.assertEqual(
            {result["title"] for result in account.full_sync_results},
            {"Anime One", "Manga One"},
        )

    def test_full_sync_ignores_the_per_item_toggle(self):
        """Turning off per-item sync doesn't stop "Sync All Now"/scheduled full syncs."""
        make_mal_account(self.user, per_item_sync_enabled=False)
        with patch("integrations.mal_sync.push_status") as mock_push:
            tasks.bulk_sync_mal_status(user_id=self.user.pk)

        pushed = {call.args[0] for call in mock_push.call_args_list}
        self.assertEqual(pushed, {self.anime, self.manga})

    def test_skips_media_with_no_status(self):
        """Statusless imported media is omitted from a full sync."""
        make_mal_account(self.user)
        Anime.objects.filter(pk=self.anime.pk).update(status=None)

        with patch("integrations.mal_sync.push_status") as mock_push:
            tasks.bulk_sync_mal_status(user_id=self.user.pk)

        mock_push.assert_called_once_with(self.manga, self.user.mal_account)

    def test_stops_and_breaks_connection_on_auth_error(self):
        """An auth failure partway through stops the batch and disables sync."""
        account = make_mal_account(self.user)
        with patch(
            "integrations.mal_sync.push_status",
            side_effect=mal_sync.MALAuthError("expired"),
        ) as mock_push:
            tasks.bulk_sync_mal_status(user_id=self.user.pk)

        account.refresh_from_db()
        self.assertTrue(account.connection_broken)
        self.assertFalse(account.sync_enabled)
        self.assertEqual(account.full_sync_status, "failed")
        self.assertEqual(account.full_sync_failed, 1)
        self.assertEqual(account.full_sync_results[0]["reason"], "expired")
        self.assertEqual(mock_push.call_count, 1)

    def test_continues_and_records_failures(self):
        """A non-auth failure on one entry doesn't abort the rest of the batch."""
        make_mal_account(self.user)
        error = ProviderAPIError("MAL", MagicMock(response=MagicMock(status_code=404)))
        with patch("integrations.mal_sync.push_status", side_effect=[error, None]):
            tasks.bulk_sync_mal_status(user_id=self.user.pk)

        account = MALAccount.objects.get(user=self.user)
        self.assertIn("1 of 2", account.last_error_message)
        self.assertEqual(account.full_sync_status, "completed")
        self.assertEqual(account.full_sync_succeeded, 1)
        self.assertEqual(account.full_sync_failed, 1)
        failed_result = next(
            result
            for result in account.full_sync_results
            if result["outcome"] == "failed"
        )
        self.assertTrue(failed_result["reason"])


class FullSyncEntriesFilters(TestCase):
    """Test the account-level status/rating filters applied to a full sync."""

    def setUp(self):
        self.user = _make_user()
        self.account = make_mal_account(self.user)
        with patch("integrations.tasks.sync_mal_status.delay"):
            self.completed = Anime.objects.create(
                user=self.user,
                item=Item.objects.create(
                    media_id="1",
                    source=Sources.MAL.value,
                    media_type=MediaTypes.ANIME.value,
                    title="Completed Anime",
                ),
                status=Status.COMPLETED.value,
                score=Decimal(8),
            )
            self.in_progress = Anime.objects.create(
                user=self.user,
                item=Item.objects.create(
                    media_id="2",
                    source=Sources.MAL.value,
                    media_type=MediaTypes.ANIME.value,
                    title="In Progress Anime",
                ),
                status=Status.IN_PROGRESS.value,
                score=Decimal(7),
            )
            self.dropped = Anime.objects.create(
                user=self.user,
                item=Item.objects.create(
                    media_id="3",
                    source=Sources.MAL.value,
                    media_type=MediaTypes.ANIME.value,
                    title="Dropped Anime",
                ),
                status=Status.DROPPED.value,
                score=Decimal(6),
            )
            self.planning = Anime.objects.create(
                user=self.user,
                item=Item.objects.create(
                    media_id="4",
                    source=Sources.MAL.value,
                    media_type=MediaTypes.ANIME.value,
                    title="Planning Anime",
                ),
                status=Status.PLANNING.value,
            )
            self.paused = Anime.objects.create(
                user=self.user,
                item=Item.objects.create(
                    media_id="5",
                    source=Sources.MAL.value,
                    media_type=MediaTypes.ANIME.value,
                    title="Paused Anime",
                ),
                status=Status.PAUSED.value,
            )
            self.unrated_dropped = Anime.objects.create(
                user=self.user,
                item=Item.objects.create(
                    media_id="6",
                    source=Sources.MAL.value,
                    media_type=MediaTypes.ANIME.value,
                    title="Unrated Dropped Anime",
                ),
                status=Status.DROPPED.value,
                score=None,
            )

    def test_defaults_include_watched_and_dropped_but_not_planning_or_paused(self):
        entries = mal_sync.full_sync_entries(self.user, self.account)

        self.assertEqual(
            {media.item.title for media in entries},
            {
                "Completed Anime",
                "In Progress Anime",
                "Dropped Anime",
                "Unrated Dropped Anime",
            },
        )

    def test_unchecking_watched_drops_completed_and_in_progress(self):
        self.account.sync_filter_watched = False
        self.account.save(update_fields=["sync_filter_watched"])

        entries = mal_sync.full_sync_entries(self.user, self.account)

        self.assertEqual(
            {media.item.title for media in entries},
            {"Dropped Anime", "Unrated Dropped Anime"},
        )

    def test_unchecking_dropped_drops_dropped_entries(self):
        self.account.sync_filter_dropped = False
        self.account.save(update_fields=["sync_filter_dropped"])

        entries = mal_sync.full_sync_entries(self.user, self.account)

        self.assertEqual(
            {media.item.title for media in entries},
            {"Completed Anime", "In Progress Anime"},
        )

    def test_rated_only_excludes_entries_without_a_score(self):
        self.account.sync_filter_rated_only = True
        self.account.save(update_fields=["sync_filter_rated_only"])

        entries = mal_sync.full_sync_entries(self.user, self.account)

        self.assertEqual(
            {media.item.title for media in entries},
            {"Completed Anime", "In Progress Anime", "Dropped Anime"},
        )

    def test_no_account_includes_watched_and_dropped_only(self):
        """Without an account to read filters from, fall back to the defaults."""
        entries = mal_sync.full_sync_entries(self.user)

        self.assertEqual(
            {media.item.title for media in entries},
            {
                "Completed Anime",
                "In Progress Anime",
                "Dropped Anime",
                "Unrated Dropped Anime",
            },
        )


class MALSyncFiltersView(TestCase):
    """Test the view that saves the full-sync status/rating filters."""

    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)

    def test_without_account_shows_error(self):
        response = self.client.post(reverse("mal_sync_filters_save"), follow=True)
        self.assertContains(response, "Connect a MyAnimeList account")

    def test_saves_selected_filters(self):
        account = make_mal_account(self.user)
        response = self.client.post(
            reverse("mal_sync_filters_save"),
            {"dropped": "on", "rated_only": "on"},
            follow=True,
        )

        self.assertContains(response, "sync filters saved")
        account.refresh_from_db()
        self.assertFalse(account.sync_filter_watched)
        self.assertTrue(account.sync_filter_dropped)
        self.assertTrue(account.sync_filter_rated_only)


class MALFullSyncView(TestCase):
    """Test the "Sync All Now" view."""

    def setUp(self):
        """Create and log in a user."""
        self.user = _make_user()
        self.client.force_login(self.user)

    def test_without_account_shows_error(self):
        """No connection at all shows a clear error, no task queued."""
        with patch("integrations.tasks.bulk_sync_mal_status.delay") as mock_delay:
            response = self.client.post(reverse("mal_full_sync"), follow=True)
        mock_delay.assert_not_called()
        self.assertContains(response, "Connect a MyAnimeList account")

    def test_broken_connection_shows_error(self):
        """A broken connection blocks a full sync until reconnected."""
        make_mal_account(self.user, connection_broken=True)
        with patch("integrations.tasks.bulk_sync_mal_status.delay") as mock_delay:
            response = self.client.post(reverse("mal_full_sync"), follow=True)
        mock_delay.assert_not_called()
        self.assertContains(response, "Reconnect")

    def test_healthy_connection_queues_task(self):
        """A working connection queues the background task for this user."""
        make_mal_account(self.user)
        with patch("integrations.tasks.bulk_sync_mal_status.delay") as mock_delay:
            response = self.client.post(
                reverse("mal_full_sync"), {"confirmed": "true"}, follow=True
            )
        mock_delay.assert_called_once_with(user_id=self.user.pk)
        self.assertContains(response, "started in the background")
        account = MALAccount.objects.get(user=self.user)
        self.assertEqual(account.full_sync_status, "queued")
        self.assertEqual(account.full_sync_results, [])

    def test_active_sync_is_not_queued_twice(self):
        account = make_mal_account(self.user)
        account.full_sync_status = "running"
        account.save(update_fields=["full_sync_status"])

        with patch("integrations.tasks.bulk_sync_mal_status.delay") as mock_delay:
            response = self.client.post(
                reverse("mal_full_sync"), {"confirmed": "true"}, follow=True
            )

        mock_delay.assert_not_called()
        self.assertContains(response, "already in progress")

    def test_status_returns_latest_persisted_progress(self):
        account = make_mal_account(self.user)
        account.full_sync_status = "running"
        account.full_sync_total = 4
        account.full_sync_processed = 2
        account.full_sync_succeeded = 1
        account.full_sync_failed = 1
        account.full_sync_results = [
            {
                "title": "Failed Anime",
                "media_type": "Anime",
                "mal_id": "42",
                "outcome": "failed",
                "reason": "Not found",
            }
        ]
        account.save()

        response = self.client.get(reverse("mal_full_sync_status"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["processed"], 2)
        self.assertTrue(response.json()["is_active"])
        self.assertEqual(response.json()["results"][0]["reason"], "Not found")

    def test_status_does_not_expose_another_users_sync(self):
        other_user = _make_user(username="other")
        make_mal_account(other_user)

        response = self.client.get(reverse("mal_full_sync_status"))

        self.assertEqual(response.status_code, 404)

    def test_full_sync_requires_preview_confirmation(self):
        make_mal_account(self.user)
        with patch("integrations.tasks.bulk_sync_mal_status.delay") as mock_delay:
            response = self.client.post(reverse("mal_full_sync"), follow=True)
        mock_delay.assert_not_called()
        self.assertContains(response, "Review the MyAnimeList changes")

    @patch("integrations.mal_sync.preview_full_sync")
    def test_preview_returns_changes_without_queuing_sync(self, mock_preview):
        make_mal_account(self.user)
        mock_preview.return_value = [
            {
                "title": "Changed Anime",
                "media_type": "Anime",
                "mal_id": "42",
                "not_on_list": False,
                "changes": [
                    {"field": "Status", "from": "watching", "to": "completed"}
                ],
            }
        ]

        with patch("integrations.tasks.bulk_sync_mal_status.delay") as mock_delay:
            response = self.client.get(reverse("mal_full_sync_preview"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        mock_delay.assert_not_called()


class MultiUserIsolation(TestCase):
    """Confirm each user's sync is scoped to their own MAL connection only."""

    def setUp(self):
        """Create two users, each with their own MAL account and anime entry."""
        self.alice = _make_user(username="alice")
        self.bob = _make_user(username="bob")
        self.alice_account = make_mal_account(self.alice)
        self.bob_account = make_mal_account(self.bob)

        with patch("integrations.tasks.sync_mal_status.delay"):
            self.alice_anime = Anime.objects.create(
                user=self.alice,
                item=Item.objects.create(
                    media_id="1",
                    source=Sources.MAL.value,
                    media_type=MediaTypes.ANIME.value,
                    title="Alice's Anime",
                ),
                status=Status.PLANNING.value,
            )
            self.bob_anime = Anime.objects.create(
                user=self.bob,
                item=Item.objects.create(
                    media_id="2",
                    source=Sources.MAL.value,
                    media_type=MediaTypes.ANIME.value,
                    title="Bob's Anime",
                ),
                status=Status.PLANNING.value,
            )

    def test_updating_one_users_anime_only_uses_their_own_account(self):
        """Syncing Alice's entry pushes through Alice's account, never Bob's."""
        with patch("integrations.mal_sync.push_status") as mock_push:
            tasks.sync_mal_status(media_type="anime", media_id=self.alice_anime.pk)
        mock_push.assert_called_once_with(self.alice_anime, self.alice_account)

    def test_disconnecting_one_account_leaves_the_other_untouched(self):
        """Disconnecting Alice's account never affects Bob's connection."""
        self.client.force_login(self.alice)
        self.client.post(reverse("mal_disconnect"))
        self.assertFalse(MALAccount.objects.filter(user=self.alice).exists())
        self.assertTrue(MALAccount.objects.filter(user=self.bob).exists())
