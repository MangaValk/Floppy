from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from app.models import Item, Sources, WatchState
from integrations import plex as plex_api
from integrations import plex_watched_push
from integrations.models import ExternalReference, PlexAccount


def _response(status=200, payload=None):
    response = Mock()
    response.status_code = status
    response.headers = {"Content-Type": "application/json"}
    response.json.return_value = payload or {}
    response.raise_for_status.return_value = None
    return response


class SwitchHomeUserTests(TestCase):
    """switch_home_user() returns a per-request token for one Home user."""

    @patch("integrations.plex.requests.post")
    def test_returns_home_user_token_and_sends_pin(self, mock_post):
        mock_post.return_value = _response(payload={"authToken": "home-token"})

        token = plex_api.switch_home_user("owner-token", "uuid-1", pin="1234")

        self.assertEqual(token, "home-token")
        self.assertTrue(mock_post.call_args.args[0].endswith("/users/uuid-1/switch"))
        self.assertEqual(mock_post.call_args.kwargs["params"], {"pin": "1234"})
        self.assertEqual(
            mock_post.call_args.kwargs["headers"]["X-Plex-Token"],
            "owner-token",
        )

    @patch("integrations.plex.requests.post")
    def test_wrong_pin_is_an_auth_error(self, mock_post):
        mock_post.return_value = _response(status=403)

        with self.assertRaises(plex_api.PlexAuthError):
            plex_api.switch_home_user("owner-token", "uuid-1", pin="0000")

    @patch("integrations.plex.requests.post")
    def test_missing_token_is_an_error(self, mock_post):
        mock_post.return_value = _response(payload={})

        with self.assertRaises(plex_api.PlexClientError):
            plex_api.switch_home_user("owner-token", "uuid-1")


class MarkWatchedTests(TestCase):
    """mark_watched() scrobbles exactly one rating key as the token's user."""

    @patch("integrations.plex.requests.get")
    def test_scrobbles_one_rating_key(self, mock_get):
        mock_get.return_value = _response()

        plex_api.mark_watched("user-token", "http://plex.local:32400", "123")

        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args.args[0], "http://plex.local:32400/:/scrobble")
        self.assertEqual(
            mock_get.call_args.kwargs["params"],
            {"key": "123", "identifier": "com.plexapp.plugins.library"},
        )
        self.assertEqual(
            mock_get.call_args.kwargs["headers"]["X-Plex-Token"],
            "user-token",
        )

    @patch("integrations.plex.requests.get")
    def test_rejected_token_is_an_auth_error(self, mock_get):
        mock_get.return_value = _response(status=401)

        with self.assertRaises(plex_api.PlexAuthError):
            plex_api.mark_watched("bad-token", "http://plex.local:32400", "123")


class FetchSectionItemTypeTests(TestCase):
    """fetch_section_all_items() can list episodes of a TV section in bulk."""

    @patch("integrations.plex.requests.get")
    def test_item_type_is_sent_only_when_given(self, mock_get):
        mock_get.return_value = _response(payload={"MediaContainer": {"Metadata": []}})

        plex_api.fetch_section_all_items("t", "http://plex.local", "2", item_type=4)
        self.assertEqual(mock_get.call_args.kwargs["params"]["type"], 4)

        plex_api.fetch_section_all_items("t", "http://plex.local", "2")
        self.assertNotIn("type", mock_get.call_args.kwargs["params"])


class SwitchHomeUserIdentityTests(TestCase):
    """switch_home_user() refuses a token for a different user."""

    @patch("integrations.plex.requests.post")
    def test_mismatched_user_is_refused(self, mock_post):
        mock_post.return_value = _response(
            payload={"uuid": "someone-else", "authToken": "t"},
        )

        with self.assertRaises(plex_api.PlexClientError):
            plex_api.switch_home_user("owner-token", "uuid-1")


class ListHomeUsersTests(TestCase):
    """list_home_users() surfaces failures instead of an empty Home."""

    @patch("integrations.plex.requests.get")
    def test_returns_users(self, mock_get):
        mock_get.return_value = _response(payload={"users": [{"uuid": "u1"}]})

        self.assertEqual(plex_api.list_home_users("t"), [{"uuid": "u1"}])

    @patch("integrations.plex.requests.get")
    def test_rejected_token_raises(self, mock_get):
        mock_get.return_value = _response(status=401)

        with self.assertRaises(plex_api.PlexAuthError):
            plex_api.list_home_users("t")


HOME_USERS = [
    {"uuid": "owner", "title": "Owner", "admin": True, "protected": True},
    {"uuid": "kid", "title": "Kid", "admin": False, "protected": False},
    {"uuid": "locked", "title": "Locked", "admin": False, "protected": True},
]
OWNED = {"machine_identifier": "srv", "name": "Home", "owned": True}
FRIENDS = {"machine_identifier": "other", "name": "Friend", "owned": False}


def _resources(token):
    """Each token sees the owned server with its own access token."""
    if token == "owner-token":
        return [{**OWNED, "access_token": "owner-srv"}, FRIENDS]
    return [{**OWNED, "access_token": f"{token}-srv", "owned": False}]


@patch("integrations.plex.list_resources", side_effect=_resources)
@patch("integrations.plex.list_home_users", return_value=HOME_USERS)
class OpenSessionTests(TestCase):
    """open_session() writes only as the chosen user on an owned server."""

    def setUp(self):
        self.account = Mock(
            plex_token="owner-token",
            sections=[{"machine_identifier": "srv", "uri": "http://plex.local"}],
        )

    def test_lists_owner_home_users_and_owned_servers_only(self, *_mocks):
        users, servers = plex_watched_push.list_targets(self.account)

        self.assertEqual([u.uuid for u in users], ["owner", "kid", "locked"])
        self.assertTrue(users[0].is_owner)
        self.assertEqual([s.machine_identifier for s in servers], ["srv"])

    @patch("integrations.plex.switch_home_user")
    def test_owner_uses_own_token_without_switching(self, mock_switch, *_mocks):
        session = plex_watched_push.open_session(self.account, "owner", "srv")

        mock_switch.assert_not_called()
        self.assertEqual(session.token, "owner-srv")
        self.assertEqual(session.uri, "http://plex.local")

    @patch("integrations.plex.switch_home_user", return_value="kid-token")
    def test_home_user_writes_with_their_own_server_token(self, mock_switch, *_m):
        session = plex_watched_push.open_session(self.account, "kid", "srv")

        mock_switch.assert_called_once_with("owner-token", "kid", None)
        self.assertEqual(session.token, "kid-token-srv")
        self.assertEqual(session.target.title, "Kid")

    @patch("integrations.plex.switch_home_user")
    def test_protected_user_needs_pin(self, mock_switch, *_mocks):
        with self.assertRaises(plex_watched_push.PinRequiredError):
            plex_watched_push.open_session(self.account, "locked", "srv")
        mock_switch.assert_not_called()

    def test_unknown_user_is_refused(self, *_mocks):
        with self.assertRaises(plex_watched_push.PlexPushError):
            plex_watched_push.open_session(self.account, "stranger", "srv")

    def test_server_not_owned_is_refused(self, *_mocks):
        with self.assertRaises(plex_watched_push.PlexPushError):
            plex_watched_push.open_session(self.account, "owner", "other")

    def test_uncached_server_address_is_refused(self, *_mocks):
        self.account.sections = []
        with self.assertRaises(plex_watched_push.PlexPushError):
            plex_watched_push.open_session(self.account, "owner", "srv")


def _movie(rating_key, tmdb_id, view_count=0, title="Movie"):
    return {
        "ratingKey": rating_key,
        "title": title,
        "year": 2000,
        "viewCount": view_count,
        "Guid": [{"id": f"tmdb://{tmdb_id}"}],
    }


def _episode(rating_key, show_key, season, number, view_count=0, title=""):
    return {
        "ratingKey": rating_key,
        "grandparentRatingKey": show_key,
        "grandparentTitle": "Show",
        "parentIndex": season,
        "index": number,
        "title": title,
        "viewCount": view_count,
    }


class BuildPlanTests(TestCase):
    """build_plan() reads both sides and plans only safe, exact writes."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="u", password="p")
        self.account = PlexAccount.objects.create(
            user=self.user,
            plex_token="owner-token",
            plex_username="owner",
            plex_account_id="acct",
            sections=[
                {"id": "1", "type": "movie", "title": "Movies",
                 "machine_identifier": "srv", "uri": "http://plex.local"},
                {"id": "2", "type": "show", "title": "TV",
                 "machine_identifier": "srv", "uri": "http://plex.local"},
                {"id": "9", "type": "movie", "title": "Elsewhere",
                 "machine_identifier": "other", "uri": "http://other"},
            ],
        )
        self.session = plex_watched_push.PushSession(
            target=plex_watched_push.PushTarget("kid", "Kid", False, False),
            server=plex_watched_push.PushServer("srv", "Home"),
            uri="http://plex.local",
            token="kid-srv",
        )
        self.library = {
            ("1", None): [],
            ("2", None): [{"ratingKey": "s1", "Guid": [{"id": "tmdb://1399"}]}],
            ("2", 4): [],
        }

    def _fetch(self, _token, _uri, section_id, start=0, item_type=None, **_kw):
        if section_id == "9":
            msg = "should never read another server"
            raise AssertionError(msg)
        entries = self.library[(section_id, item_type)]
        return entries[start:start + 2], len(entries)

    def _watched(self, media_id, media_type="movie", **fields):
        item = Item.objects.create(
            media_id=media_id,
            source=Sources.TMDB.value,
            media_type=media_type,
            title=fields.pop("title", f"Item {media_id}"),
            **fields,
        )
        WatchState.objects.create(user=self.user, item=item, watched=True)
        return item

    def _reference(self, rating_key, media_type, review_status="resolved", **fields):
        return ExternalReference.objects.create(
            user=self.user,
            integration="plex",
            source_account="srv::acct",
            external_namespace="plex_rating_key",
            external_identity=rating_key,
            media_type=media_type,
            review_status=review_status,
            **fields,
        )

    def _plan(self):
        with (
            patch("integrations.plex.fetch_section_all_items", side_effect=self._fetch),
            patch("integrations.plex.mark_watched") as mark,
            patch("integrations.plex.requests.post") as post,
        ):
            plan = plex_watched_push.build_plan(self.user, self.account, self.session)
        mark.assert_not_called()
        post.assert_not_called()
        return plan

    def test_plans_only_floppy_watched_movies_unwatched_in_plex(self):
        matrix = self._watched("603")
        self._watched("604")
        self.library[("1", None)] = [
            _movie("m1", 603, title="The Matrix"),
            _movie("m2", 604, view_count=2),
            _movie("m3", 999),
        ]

        plan = self._plan()

        self.assertEqual([w.rating_key for w in plan.writes], ["m1"])
        self.assertEqual(plan.writes[0].item_id, matrix.id)
        self.assertEqual(plan.writes[0].plex_title, "The Matrix (2000)")
        self.assertEqual(plan.already_watched, 1)

    def test_unknown_view_count_is_never_treated_as_unwatched(self):
        self._watched("603")
        self.library[("1", None)] = [_movie("m1", 603, view_count="?")]

        self.assertEqual(self._plan().writes, [])

    def test_ignored_decision_is_never_written(self):
        self._watched("603")
        self._reference("m1", "movie", review_status="ignored")
        self.library[("1", None)] = [_movie("m1", 603)]

        plan = self._plan()

        self.assertEqual(plan.writes, [])
        self.assertEqual(plan.ignored, 1)

    def test_corrected_decision_wins_over_plex_ids(self):
        self._watched("603")
        unwatched = Item.objects.create(
            media_id="605", source=Sources.TMDB.value, media_type="movie", title="X",
        )
        self._reference("m1", "movie", corrected_item=unwatched)
        self.library[("1", None)] = [_movie("m1", 603)]

        # Plex says 603, but the user corrected it to 605, which is unwatched.
        self.assertEqual(self._plan().writes, [])

    def test_plans_episode_by_show_id_and_numbers(self):
        episode = self._watched(
            "1399", "episode", season_number=1, episode_number=1,
            title="Winter Is Coming",
        )
        self.library[("2", 4)] = [
            _episode("e1", "s1", 1, 1, title="Winter Is Coming"),
            _episode("e2", "s1", 1, 2),
        ]

        plan = self._plan()

        self.assertEqual([w.rating_key for w in plan.writes], ["e1"])
        self.assertEqual(plan.writes[0].item_id, episode.id)
        self.assertEqual(plan.writes[0].plex_title, "Show S01E01 Winter Is Coming")
        self.assertEqual(plan.writes[0].warning, "")

    def test_differing_episode_titles_are_flagged(self):
        self._watched(
            "1399", "episode", season_number=1, episode_number=1, title="Pilot",
        )
        self.library[("2", 4)] = [_episode("e1", "s1", 1, 1, title="Something Else")]

        self.assertTrue(self._plan().writes[0].warning)

    def test_generic_or_show_titles_are_not_flagged(self):
        self._watched("1399", "episode", season_number=1, episode_number=1,
                      title="Show")
        self._watched("1399", "episode", season_number=1, episode_number=2,
                      title="Real Title")
        self.library[("2", 4)] = [
            _episode("e1", "s1", 1, 1, title="Winter Is Coming"),
            _episode("e2", "s1", 1, 2, title="Episode 2"),
        ]

        self.assertEqual([w.warning for w in self._plan().writes], ["", ""])

    def test_anime_episode_without_exact_decision_is_not_written(self):
        self._watched(
            "1399", "episode", season_number=1, episode_number=1,
            library_media_type="anime",
        )
        self.library[("2", 4)] = [_episode("e1", "s1", 1, 1)]

        plan = self._plan()

        self.assertEqual(plan.writes, [])
        self.assertEqual(len(plan.not_matched), 1)

    def test_anime_episode_with_exact_decision_is_written(self):
        episode = self._watched(
            "1399", "episode", season_number=1, episode_number=1,
            library_media_type="anime",
        )
        self._reference("e1", "episode", matched_item=episode)
        self.library[("2", 4)] = [_episode("e1", "s1", 3, 7)]

        self.assertEqual(self._plan().writes[0].item_id, episode.id)

    def test_show_decision_maps_episode_numbers(self):
        show = Item.objects.create(
            media_id="1400", source=Sources.TMDB.value, media_type="tv", title="S",
        )
        episode = self._watched("1400", "episode", season_number=2, episode_number=1)
        self._reference(
            "s1", "tv", matched_item=show, episode_mapping={"1:13": [2, 1]},
        )
        self.library[("2", 4)] = [_episode("e1", "s1", 1, 13)]

        self.assertEqual(self._plan().writes[0].item_id, episode.id)

    def test_unreadable_library_is_reported_and_others_continue(self):
        self._watched("1399", "episode", season_number=1, episode_number=1)
        self.library[("2", 4)] = [_episode("e1", "s1", 1, 1)]
        original = self._fetch

        def fetch(token, uri, section_id, **kwargs):
            if section_id == "1":
                msg = "denied"
                raise plex_api.PlexAuthError(msg)
            return original(token, uri, section_id, **kwargs)

        self._fetch = fetch
        plan = self._plan()

        self.assertEqual(plan.failed_libraries, ["Movies"])
        self.assertEqual([w.rating_key for w in plan.writes], ["e1"])

    def test_pages_through_large_libraries(self):
        for media_id in ("1", "2", "3"):
            self._watched(media_id)
        self.library[("1", None)] = [
            _movie("m1", 1), _movie("m2", 2), _movie("m3", 3),
        ]

        self.assertEqual(len(self._plan().writes), 3)


class PlexPushViewTests(TestCase):
    """The Plex modal reads only, and offers no way to send yet."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="v", password="p")
        self.client.force_login(self.user)
        self.session = plex_watched_push.PushSession(
            target=plex_watched_push.PushTarget("kid", "Kid", False, False),
            server=plex_watched_push.PushServer("srv", "Home"),
            uri="http://plex.local",
            token="kid-srv",
        )

    def _connect(self):
        return PlexAccount.objects.create(
            user=self.user, plex_token="owner-token", plex_username="owner",
        )

    def _write(self, rating_key, warning=""):
        return plex_watched_push.PlannedWrite(
            rating_key=rating_key, item_id=1, media_type="movie", library="Movies",
            plex_title=f"Title {rating_key}", floppy_title="Floppy title",
            warning=warning,
        )

    def test_page_row_follows_the_plex_connection(self):
        def state():
            page = self.client.get(reverse("mal_export"))
            services = {s["slug"]: s for s in page.context["outbound_services"]}
            return services["plex"]["state"], page

        status, page = state()
        self.assertEqual(status, "off")
        self.assertContains(page, "Connect Plex on the")

        self._connect()
        with patch("integrations.plex.list_home_users") as users:
            status, page = state()
        # Opening the page never calls plex.tv; users load on request.
        users.assert_not_called()
        self.assertEqual(status, "connected")
        self.assertContains(page, reverse("plex_push_targets"))

    @patch(
        "integrations.plex_watched_push.list_targets",
        return_value=(
            [plex_watched_push.PushTarget("kid", "Kid", False, True)],
            [plex_watched_push.PushServer("srv", "Home")],
        ),
    )
    def test_targets_lists_users_and_servers(self, _targets):
        self._connect()

        response = self.client.get(reverse("plex_push_targets"))

        self.assertContains(response, 'value="kid"')
        self.assertContains(response, 'value="srv"')
        self.assertContains(response, reverse("plex_push_preview"))

    def test_targets_without_plex_asks_to_connect(self):
        self.assertContains(self.client.get(reverse("plex_push_targets")), "Connect Plex first.")

    @patch("integrations.plex.mark_watched")
    def test_preview_lists_writes_and_cannot_send(self, mark):
        self._connect()
        plan = plex_watched_push.PushPlan(
            writes=[self._write("m1"), self._write("m2", warning="Titles differ")],
            already_watched=4,
            not_matched=[("Anime S01E01", "numbering may differ")],
            failed_libraries=["Kids"],
        )
        with (
            patch("integrations.plex_watched_push.open_session", return_value=self.session),
            patch("integrations.plex_watched_push.build_plan", return_value=plan),
        ):
            response = self.client.post(
                reverse("plex_push_preview"),
                {"user_uuid": "kid", "machine_identifier": "srv"},
            )

        content = response.content.decode()
        self.assertIn('value="m1:1" class="mt-1 shrink-0" checked', content)
        self.assertIn('value="m2:1" class="mt-1 shrink-0">', content)
        self.assertIn("Titles differ", content)
        self.assertIn("4 already watched in Plex", content)
        self.assertIn("Could not read: Kids", content)
        self.assertIn("Anime S01E01", content)
        self.assertIn("disabled", content)
        self.assertNotIn("hx-post", content)
        mark.assert_not_called()

    def test_preview_reports_a_missing_pin(self):
        self._connect()
        with patch(
            "integrations.plex_watched_push.open_session",
            side_effect=plex_watched_push.PinRequiredError("Kid needs their Plex PIN"),
        ):
            response = self.client.post(reverse("plex_push_preview"), {"user_uuid": "kid"})

        self.assertContains(response, "Kid needs their Plex PIN")

    def test_preview_runs_one_check_at_a_time(self):
        self._connect()
        cache.add(f"plex_push_preview:{self.user.pk}", 1)
        with patch("integrations.plex_watched_push.open_session") as session:
            response = self.client.post(reverse("plex_push_preview"), {})

        session.assert_not_called()
        self.assertContains(response, "A check is already running")
        cache.delete(f"plex_push_preview:{self.user.pk}")

    def test_preview_is_post_only(self):
        self._connect()
        self.assertEqual(self.client.get(reverse("plex_push_preview")).status_code, 405)
