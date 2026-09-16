"""Celery tasks for pushing watch status to MyAnimeList.

Send-only: these tasks push Floppy's status/progress/score to MyAnimeList and
never pull changes back (that's the separate MAL import in integrations.imports.mal).
"""

import logging

import requests
from celery import shared_task
from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone

from app.models.choices import Sources
from app.providers import services
from integrations import mal_sync
from integrations.models import MALAccount

logger = logging.getLogger(__name__)

MAL_SYNC_TASK_NAME = "Sync status to MyAnimeList"
MAL_FULL_SYNC_TASK_NAME = "Full sync to MyAnimeList"


def _mark_connection_broken(mal_account, message):
    """Disable sync and record why, matching the LastFM/Koito account pattern."""
    mal_account.connection_broken = True
    mal_account.sync_enabled = False
    mal_account.last_error_message = str(message)[:500]
    mal_account.last_failed_at = timezone.now()
    mal_account.save(
        update_fields=[
            "connection_broken",
            "sync_enabled",
            "last_error_message",
            "last_failed_at",
            "updated_at",
        ],
    )


@shared_task(
    name=MAL_SYNC_TASK_NAME,
    autoretry_for=(services.ProviderAPIError,),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def sync_mal_status(media_type, media_id):
    """Push a single anime/manga entry's status, progress and score to MyAnimeList.

    Runs after every save() of a MAL-backed Anime/Manga instance (see the
    save() overrides in app.models.media). Silently no-ops if the entry, the
    user's MAL connection, or sync itself is gone by the time this runs -
    it's a best-effort mirror of Floppy's data, not a source of truth.
    """
    model = apps.get_model(app_label="app", model_name=media_type)
    # Anime's default manager hides rows auto-migrated to episode tracking on
    # completion; all_objects (Anime only) still finds them for this one-off push.
    manager = model.all_objects if hasattr(model, "all_objects") else model.objects

    try:
        media = manager.select_related("item", "user", "user__mal_account").get(
            pk=media_id,
        )
    except model.DoesNotExist:
        logger.info(
            "%s %s no longer exists, skipping MyAnimeList sync",
            media_type,
            media_id,
        )
        return

    try:
        mal_account = media.user.mal_account
    except MALAccount.DoesNotExist:
        return

    if not mal_account.sync_enabled or mal_account.connection_broken:
        return

    if media.status is None:
        return

    try:
        mal_sync.push_status(media, mal_account)
    except mal_sync.MALAuthError as error:
        _mark_connection_broken(mal_account, error)
    except services.ProviderAPIError as error:
        if error.status_code in {requests.codes.not_found, requests.codes.bad_request}:
            logger.warning(
                "MyAnimeList rejected the update for %s (MAL ID %s): %s",
                media.item.title,
                media.item.media_id,
                error,
            )
            return
        raise


@shared_task(name=MAL_FULL_SYNC_TASK_NAME)
def bulk_sync_mal_status(user_id):
    """Push every MAL-backed anime/manga entry's current status to MyAnimeList.

    Runs on demand (the "Sync All Now" button) rather than per save() - useful
    right after connecting an account with an existing library, or after a
    bulk import/restore, since those bypass save() and never queue a sync.
    """
    Anime = apps.get_model(app_label="app", model_name="anime")  # noqa: N806
    Manga = apps.get_model(app_label="app", model_name="manga")  # noqa: N806

    try:
        user = get_user_model().objects.select_related("mal_account").get(pk=user_id)
    except get_user_model().DoesNotExist:
        return

    try:
        mal_account = user.mal_account
    except MALAccount.DoesNotExist:
        return

    if not mal_account.sync_enabled or mal_account.connection_broken:
        return

    entries = [
        *Anime.all_objects.filter(
            user=user,
            item__source=Sources.MAL.value,
            status__isnull=False,
        ),
        *Manga.objects.filter(
            user=user,
            item__source=Sources.MAL.value,
            status__isnull=False,
        ),
    ]

    synced = 0
    failed = 0
    for media in entries:
        try:
            mal_sync.push_status(media, mal_account)
            synced += 1
        except mal_sync.MALAuthError as error:
            _mark_connection_broken(mal_account, error)
            return
        except services.ProviderAPIError as error:
            logger.warning(
                "Full MyAnimeList sync: failed to push %s (MAL ID %s): %s",
                media.item.title,
                media.item.media_id,
                error,
            )
            failed += 1
        except Exception:
            logger.exception(
                "Full MyAnimeList sync: unexpected failure pushing %s (MAL ID %s)",
                media.item.title,
                media.item.media_id,
            )
            failed += 1

    logger.info(
        "Full MyAnimeList sync for %s: %s updated, %s failed (%s total)",
        user,
        synced,
        failed,
        len(entries),
    )
    if failed:
        # A per-item failure (e.g. one deleted MAL entry) isn't a broken
        # connection - leave sync_enabled/connection_broken alone, just
        # surface it the same way an ongoing sync error would show up.
        mal_account.last_error_message = (
            f"Last full sync: {failed} of {len(entries)} entries failed to "
            "update on MyAnimeList - check server logs for details."
        )[:500]
        mal_account.last_failed_at = timezone.now()
        mal_account.save(
            update_fields=["last_error_message", "last_failed_at", "updated_at"]
        )
