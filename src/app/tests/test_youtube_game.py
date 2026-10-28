"""The game YouTube tags on a video, read from its watch page."""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, tag
from django.utils import timezone

from app.models import Item, MediaTypes, Sources, VideoGameTag
from app.services import youtube_game


def _page(*games, icon="GAMING_LOGO", heading="Games"):
    """The slice of ytInitialData that carries the game section."""
    return {
        "engagementPanels": [
            {
                "items": [
                    {
                        "videoAttributesSectionViewModel": {
                            "headerTitle": heading,
                            "videoAttributeViewModels": [
                                {
                                    "videoAttributeViewModel": {
                                        "title": title,
                                        "subtitle": year,
                                        "onTap": {
                                            "innertubeCommand": {
                                                "browseEndpoint": {"browseId": game_id},
                                            },
                                        },
                                    },
                                }
                                for title, year, game_id in games
                            ],
                            "footerButton": {"buttonViewModel": {"iconName": icon}},
                        },
                    },
                ],
            },
        ],
    }


MINECRAFT = ("Minecraft", "2009", "UCQvWX73GQygcwXOTSf_VDVg")


class ExtractGamesTests(TestCase):
    def test_reads_title_year_and_game_id(self):
        self.assertEqual(
            youtube_game.extract_games(_page(MINECRAFT)),
            [{"title": "Minecraft", "game_id": MINECRAFT[2], "year": "2009"}],
        )

    def test_translated_heading_still_matches(self):
        self.assertEqual(
            len(youtube_game.extract_games(_page(MINECRAFT, heading="Spiele"))), 1
        )

    def test_a_section_without_the_gaming_icon_is_not_a_game(self):
        self.assertEqual(
            youtube_game.extract_games(_page(MINECRAFT, icon="MUSIC_LOGO")), []
        )

    def test_a_page_without_a_section_has_no_game(self):
        self.assertEqual(youtube_game.extract_games({"contents": []}), [])


class RefreshGameTagTests(TestCase):
    def setUp(self):
        self.item = Item.objects.create(
            media_id="HQp_b8VHtgI",
            source=Sources.YOUTUBE.value,
            media_type=MediaTypes.VIDEO.value,
            title="A video",
        )

    def _refresh(self, data=None, error=None):
        target = "app.services.youtube_game.fetch_initial_data"
        with patch(target, side_effect=error, return_value=data):
            return youtube_game.refresh_game_tag(self.item.pk)

    def test_found(self):
        self.assertEqual(self._refresh(_page(MINECRAFT)), "found")
        tag_row = VideoGameTag.objects.get(item=self.item)
        self.assertEqual((tag_row.game_title, tag_row.game_id), ("Minecraft", MINECRAFT[2]))

    def test_untagged_video_is_not_found_not_guessed(self):
        self.assertEqual(self._refresh({"contents": []}), "not_found")
        self.assertEqual(VideoGameTag.objects.get(item=self.item).game_title, "")

    def test_fetch_failure_is_unavailable_and_counts(self):
        err = youtube_game.WatchPageUnavailableError("boom")
        self._refresh(error=err)
        self._refresh(error=err)
        row = VideoGameTag.objects.get(item=self.item)
        self.assertEqual((row.status, row.failures), ("unavailable", 2))

    def test_recovery_after_failure_clears_the_count(self):
        self._refresh(error=youtube_game.WatchPageUnavailableError("boom"))
        self._refresh(_page(MINECRAFT))
        self.assertEqual(VideoGameTag.objects.get(item=self.item).failures, 0)

    def test_other_sources_are_ignored(self):
        self.item.source = Sources.MANUAL.value
        self.item.save()
        self.assertIsNone(self._refresh(_page(MINECRAFT)))
        self.assertFalse(VideoGameTag.objects.exists())

    def test_bad_video_id_never_reaches_the_network(self):
        with self.assertRaises(youtube_game.WatchPageUnavailableError):
            youtube_game.fetch_initial_data("../etc/passwd")


class LookupDueTests(TestCase):
    def setUp(self):
        self.item = Item.objects.create(
            media_id="HQp_b8VHtgI",
            source=Sources.YOUTUBE.value,
            media_type=MediaTypes.VIDEO.value,
            title="A video",
        )

    def _tag(self, status, age, failures=0):
        VideoGameTag.objects.create(
            item=self.item,
            status=status,
            checked_at=timezone.now() - age,
            failures=failures,
        )

    def test_new_item_is_due(self):
        self.assertTrue(youtube_game.lookup_due(self.item))

    def test_found_is_never_due_again(self):
        self._tag("found", timedelta(days=400))
        self.assertFalse(youtube_game.lookup_due(self.item))

    def test_not_found_waits_a_week(self):
        self._tag("not_found", timedelta(days=1))
        self.assertFalse(youtube_game.lookup_due(self.item))
        VideoGameTag.objects.update(checked_at=timezone.now() - timedelta(days=8))
        self.assertTrue(youtube_game.lookup_due(self.item))

    def test_unavailable_backs_off_then_gives_up(self):
        self._tag("unavailable", timedelta(minutes=5), failures=1)
        self.assertFalse(youtube_game.lookup_due(self.item))
        VideoGameTag.objects.update(checked_at=timezone.now() - timedelta(hours=7))
        self.assertTrue(youtube_game.lookup_due(self.item))
        VideoGameTag.objects.update(failures=youtube_game.MAX_FAILURES)
        self.assertFalse(youtube_game.lookup_due(self.item))


@tag("network")
class LiveWatchPageTests(TestCase):
    """Reads YouTube for real: run with `scripts/test.sh --network`."""

    def test_sample_video_is_tagged_minecraft(self):
        games = youtube_game.extract_games(
            youtube_game.fetch_initial_data("HQp_b8VHtgI")
        )
        self.assertEqual(games[0]["title"], "Minecraft")
        self.assertEqual(games[0]["game_id"], MINECRAFT[2])

    def test_untagged_video_has_no_game(self):
        self.assertEqual(
            youtube_game.extract_games(youtube_game.fetch_initial_data("dQw4w9WgXcQ")),
            [],
        )
