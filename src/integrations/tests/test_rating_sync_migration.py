"""Upgrade/rollback must preserve watched intents and local tracking scores."""

import os
from unittest import skipIf

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


def _state_targets(graph, anchor):
    """Pick migration nodes whose model state does not outrun ``anchor``.

    The test needs the other apps' models (User, Item, Movie), but a newer
    migration in those apps can depend on a later ``integrations`` migration
    and would drag its columns into the state while the database is still at
    ``anchor``. For each other app, take the newest node whose ancestors stay
    within the ``integrations`` migrations that ``anchor`` already includes.
    """
    allowed = set(graph.forwards_plan(anchor))
    targets = [anchor]
    for leaf in graph.leaf_nodes():
        if leaf[0] == "integrations":
            continue
        node = leaf
        while any(
            ancestor[0] == "integrations" and ancestor not in allowed
            for ancestor in graph.forwards_plan(node)
        ):
            parents = [
                parent
                for parent in graph.node_map[node].parents
                if parent.key[0] == node[0]
            ]
            node = parents[0].key
        targets.append(node)
    return targets


@skipIf(os.environ.get("FLOPPY_TEST_FAST_DB") == "1", "Requires the migration graph")
class RatingSyncMigrationTests(TransactionTestCase):
    """Exercise real schema operations on the configured database backend."""

    def test_watched_delivery_and_local_score_survive_upgrade_and_rollback(self):
        before = ("integrations", "0058_psn_playtime_snapshots")
        after = ("integrations", "0059_rating_sync")
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([before])
            executor = MigrationExecutor(connection)
            targets = _state_targets(executor.loader.graph, before)
            apps = executor.loader.project_state(targets).apps
            user = apps.get_model("users", "User").objects.create(
                username="migration-rating"
            )
            item = apps.get_model("app", "Item").objects.create(
                source="tmdb",
                media_type="movie",
                media_id="550",
                title="Movie",
            )
            apps.get_model("app", "Movie").objects.create(
                user_id=user.pk, item_id=item.pk, score=8
            )
            binding = apps.get_model("integrations", "SyncBinding").objects.create(
                user_id=user.pk,
                client_kind="jellyfin",
                origin_key="migration-test",
            )
            watched = apps.get_model(
                "integrations", "OutboundStateDelivery"
            ).objects.create(
                binding_id=binding.pk,
                user_id=user.pk,
                item_id=item.pk,
                target_revision=1,
                status="pending",
                intent=False,
            )
            MigrationExecutor(connection).migrate([after])
            executor = MigrationExecutor(connection)
            # The database is at ``after``, so read it with models of that
            # schema; a later migration may add columns it does not have yet.
            apps = executor.loader.project_state(
                _state_targets(executor.loader.graph, after)
            ).apps
            deliveries = apps.get_model("integrations", "OutboundStateDelivery").objects
            self.assertEqual(deliveries.get(pk=watched.pk).operation, "watched")
            self.assertFalse(deliveries.get(pk=watched.pk).intent)
            deliveries.create(
                binding_id=binding.pk,
                user_id=user.pk,
                item_id=item.pk,
                target_revision=1,
                operation="rating",
                rating=7,
            )
            executor.migrate([before])
            executor = MigrationExecutor(connection)
            apps = executor.loader.project_state(targets).apps
            surviving = apps.get_model(
                "integrations", "OutboundStateDelivery"
            ).objects.get()
            self.assertEqual(surviving.pk, watched.pk)
            self.assertEqual(surviving.status, "pending")
            self.assertFalse(surviving.intent)
            self.assertEqual(apps.get_model("app", "Movie").objects.get().score, 8)
        finally:
            MigrationExecutor(connection).migrate(latest)
