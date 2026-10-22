from unittest.mock import patch

from django.test import TestCase

from app.models import Item, MediaTypes, Sources
from app.tasks_game_groups import (
    count_game_group_backfill_items,
    populate_game_group_data_for_items,
    reconcile_game_groups_backfill,
)


class GameGroupBackfillTests(TestCase):
    def _game(self, media_id="123", **fields):
        return Item.objects.create(
            media_id=media_id,
            source=Sources.IGDB.value,
            media_type=MediaTypes.GAME.value,
            title=f"Game {media_id}",
            **fields,
        )

    @patch("app.tasks_game_groups.services.get_media_metadata")
    def test_backfill_populates_franchise_and_collection(self, mock_metadata):
        item = self._game()
        mock_metadata.return_value = {
            "provider_franchise_id": "10",
            "provider_franchise_name": "Mario",
            "provider_collection_id": "20",
            "provider_collection_name": "Super Mario",
        }

        result = populate_game_group_data_for_items([item.id])

        item.refresh_from_db()
        self.assertEqual(result["updated"], 1)
        self.assertEqual(item.provider_franchise_name, "Mario")
        self.assertEqual(item.provider_collection_name, "Super Mario")

    @patch("app.tasks_game_groups.services.get_media_metadata")
    def test_provider_without_groups_still_completes(self, mock_metadata):
        item = self._game()
        mock_metadata.return_value = {
            "provider_franchise_id": "",
            "provider_franchise_name": "",
            "provider_collection_id": "",
            "provider_collection_name": "",
        }

        result = populate_game_group_data_for_items([item.id])

        self.assertEqual(result["updated"], 1)
        self.assertEqual(count_game_group_backfill_items(), 0)

    @patch("app.tasks_game_groups.enqueue_game_group_backfill_items", return_value=1)
    def test_reconcile_selects_games_missing_group_data(self, mock_enqueue):
        self._game(
            media_id="1",
            provider_franchise_name="Mario",
            provider_collection_name="Super Mario",
        )
        missing = self._game(media_id="2")

        result = reconcile_game_groups_backfill()

        self.assertEqual(result["selected"], 1)
        self.assertEqual(mock_enqueue.call_args.args[0], [missing.id])
