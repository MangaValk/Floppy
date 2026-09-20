"""Repair anime that ended up tracked in both libraries (discussion #967).

Before the routing fix, a scrobble could land in the Anime library on one
episode and in TV Shows on the next, leaving two independent tracking rows for
one show. This folds those pairs back together.

Detection is pure database work: `_handle_anime` already wrote the show's
TMDB/TVDB identity onto the flat MAL Item as a provider link, so a duplicate is
visible without asking any provider. The merge itself needs metadata and is
therefore done here, in a retryable task, rather than in a migration where a
provider outage would fail the container's upgrade.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)

# Buckets that mean "this is not in the Anime library".
NON_ANIME_TV_BUCKETS = ("", "tv")

# A group of 1 row has nothing to merge; only 2+ rows are duplicates.
MIN_DUPLICATE_GROUP_SIZE = 2


def _provider_identities(anime_item):
    """Return the (provider, series_id) pairs a flat anime Item points at."""
    from app.models import ItemProviderLink, MediaTypes, Sources

    return [
        (link.provider, link.provider_media_id)
        for link in ItemProviderLink.objects.filter(
            item=anime_item,
            provider__in=(Sources.TMDB.value, Sources.TVDB.value),
            provider_media_type=MediaTypes.TV.value,
        )
    ]


def _find_plain_tv_duplicate(anime):
    """Return the non-anime TV row the same user tracks for this show."""
    from django.db.models import Q

    from app.models import TV, MediaTypes

    identities = _provider_identities(anime.item)
    if not identities:
        return None

    identity_filter = Q()
    for provider, series_id in identities:
        identity_filter |= Q(item__source=provider, item__media_id=series_id)

    return (
        TV.objects.filter(
            identity_filter,
            user=anime.user,
            item__media_type=MediaTypes.TV.value,
            item__library_media_type__in=NON_ANIME_TV_BUCKETS,
        )
        .select_related("item")
        .order_by("item_id")
        .first()
    )


def duplicate_pairs(batch_size=None):
    """Yield (anime, tv) pairs where one show is tracked in both libraries.

    MAL identity is per cour, so several Anime rows routinely map to one TV
    show ("Food Wars!" seasons 1 and 2 are two MAL entries and one TMDB
    series). Only one pair is yielded per stray TV row: converting the flat
    row collapses all of that user's sibling MAL entries for the same series,
    and the TV row can only be folded in once.
    """
    from app.models import Anime

    found = 0
    seen_tv_rows = set()
    queryset = Anime.objects.select_related("item", "user").order_by("id")
    for anime in queryset.iterator(chunk_size=200):
        duplicate = _find_plain_tv_duplicate(anime)
        if duplicate is None or duplicate.pk in seen_tv_rows:
            continue
        seen_tv_rows.add(duplicate.pk)
        yield anime, duplicate
        found += 1
        if batch_size is not None and found >= batch_size:
            return


def _repair_pair(anime, tv):
    """Fold one duplicate pair together. Returns a short outcome string."""
    from app.models import ItemProviderLink, MediaTypes
    from app.services import item_merge, library_migration, metadata_resolution

    target_source = metadata_resolution.metadata_default_source(
        anime.user,
        MediaTypes.ANIME.value,
    )

    if target_source not in metadata_resolution.GROUPED_ANIME_PROVIDERS:
        # The user wants flat MAL entries. The flat row is already correct, so
        # only the stray TV row has to move.
        library_migration.migrate_library_item(
            anime.user,
            tv.item,
            MediaTypes.ANIME.value,
            anime.item.source,
            anime.item.media_id,
        )
        return "merged_into_flat"

    link = ItemProviderLink.objects.filter(
        item=anime.item,
        provider=target_source,
        provider_media_type=MediaTypes.TV.value,
    ).first()
    if link is None:
        return "no_target_identity"

    # Convert the flat row into the grouped shape first: the preflight refuses
    # when grouped anime tracking already exists, and promoting the plain TV
    # row would create exactly that.
    grouped_item = library_migration.migrate_library_item(
        anime.user,
        anime.item,
        MediaTypes.ANIME.value,
        target_source,
        link.provider_media_id,
    )
    if grouped_item.pk == tv.item.pk:
        return "already_merged"

    item_merge.merge_item(loser=tv.item, keeper=grouped_item)
    return "merged_into_grouped"


@shared_task(name="Repair duplicated anime libraries")
def repair_duplicated_anime_libraries_task(batch_size: int = 25):
    """Fold shows tracked in both Anime and TV Shows back into one row.

    Best effort and idempotent: a pair that cannot be resolved safely is left
    completely untouched and reported, never guessed at. Re-running picks up
    where the last run stopped.
    """
    from app.providers.services import ProviderAPIError
    from app.services.anime_migration import AnimeMigrationError
    from app.services.library_migration import LibraryMigrationError

    repaired = 0
    skipped = 0
    unresolved = []

    for anime, tv in duplicate_pairs(batch_size=batch_size):
        title = anime.item.title
        try:
            outcome = _repair_pair(anime, tv)
        except (
            AnimeMigrationError,
            LibraryMigrationError,
            ProviderAPIError,
        ) as error:
            skipped += 1
            unresolved.append(title)
            logger.warning(
                "Left duplicated anime %r untouched: %s",
                title,
                error,
            )
            continue
        except Exception:
            skipped += 1
            unresolved.append(title)
            logger.warning(
                "Repair crashed for duplicated anime %r",
                title,
                exc_info=True,
            )
            continue

        if outcome.startswith("merged"):
            repaired += 1
            logger.info("Merged duplicated anime %r (%s)", title, outcome)
        else:
            skipped += 1
            unresolved.append(title)
            logger.warning(
                "Left duplicated anime %r untouched: %s",
                title,
                outcome,
            )

    return {
        "repaired": repaired,
        "skipped": skipped,
        "unresolved": unresolved,
    }


def duplicate_active_anime_groups(user=None):
    """Yield lists of 2+ Anime rows sharing (user, item) that are not all completed.

    Several completed rows for one show are intentional rewatch history and
    are left alone, since a script can't tell them apart from an accidental
    duplicate. But a mix of a completed row and a non-completed one (e.g. a
    12/12 completed row alongside a stray 11/12 one), or several non-completed
    rows, is never a second intentional state - a show is only ever actively
    "in progress" (or planning/paused/dropped) once at a time.
    """
    from collections import defaultdict

    from app.models import Anime
    from app.models.choices import Status

    queryset = Anime.objects.select_related("item")
    if user is not None:
        queryset = queryset.filter(user=user)

    groups = defaultdict(list)
    for anime in queryset.iterator(chunk_size=200):
        groups[(anime.user_id, anime.item_id)].append(anime)

    for rows in groups.values():
        if len(rows) < MIN_DUPLICATE_GROUP_SIZE:
            continue
        if all(row.status == Status.COMPLETED.value for row in rows):
            continue
        yield rows


def _merge_duplicate_active_group(rows):
    """Keep the row with the highest progress from a duplicate group."""
    keeper = max(rows, key=lambda row: (row.progress or 0, row.pk))
    for row in rows:
        if row.pk != keeper.pk:
            row.delete()
    return keeper


@shared_task(name="Deduplicate watched anime")
def deduplicate_watched_anime_task(user_id: int):
    """Fold duplicate Anime rows for the same show into the highest progress one.

    Skips groups where every row is completed, since that's intentional
    rewatch history a script can't tell apart from an accidental duplicate.
    Any other duplicate group - including a completed row mixed with a lower,
    stale non-completed one - is folded down to its highest progress row.
    """
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.filter(pk=user_id).first()
    if user is None:
        return {"merged": 0, "skipped": 0, "unresolved": []}

    merged = 0
    unresolved = []

    for rows in duplicate_active_anime_groups(user=user):
        title = rows[0].item.title
        try:
            _merge_duplicate_active_group(rows)
        except Exception:
            unresolved.append(title)
            logger.warning("Dedup crashed for anime %r", title, exc_info=True)
            continue
        merged += 1

    return {"merged": merged, "skipped": len(unresolved), "unresolved": unresolved}


def anime_rows_needing_conversion(user):
    """Return the user's anime Items that are not in their preferred shape.

    Switching the Anime Provider only decides the shape of newly added shows;
    existing ones are converted on request, because MAL identity is per cour
    and TMDB/TVDB identity is per show, so the mapping is N:1 and cannot be
    re-derived in bulk without losing or guessing at history.
    """
    from app.models import TV, Anime, ItemProviderLink, MediaTypes
    from app.services import metadata_resolution

    target_source = metadata_resolution.metadata_default_source(
        user,
        MediaTypes.ANIME.value,
    )

    if target_source in metadata_resolution.GROUPED_ANIME_PROVIDERS:
        linked_item_ids = ItemProviderLink.objects.filter(
            provider=target_source,
            provider_media_type=MediaTypes.TV.value,
        ).values("item_id")
        return [
            anime.item
            for anime in Anime.objects.filter(
                user=user,
                item_id__in=linked_item_ids,
            ).select_related("item")
        ]

    return [
        tv.item
        for tv in TV.objects.filter(
            user=user,
            item__media_type=MediaTypes.TV.value,
            item__library_media_type=MediaTypes.ANIME.value,
        ).select_related("item")
    ]


@shared_task(name="Convert anime library shape")
def convert_anime_library_shape_task(user_id: int):
    """Move a user's existing anime into the shape their provider implies.

    Only ever runs when the user explicitly asks for it. Titles that cannot be
    converted safely are left untouched and named in the result.
    """
    from django.contrib.auth import get_user_model

    from app.models import ItemProviderLink, MediaTypes, Sources
    from app.providers.services import ProviderAPIError
    from app.services import library_migration, metadata_resolution
    from app.services.anime_migration import AnimeMigrationError
    from app.services.library_migration import LibraryMigrationError

    user = get_user_model().objects.filter(pk=user_id).first()
    if user is None:
        return {"converted": 0, "skipped": 0, "unresolved": []}

    target_source = metadata_resolution.metadata_default_source(
        user,
        MediaTypes.ANIME.value,
    )
    wants_grouped = target_source in metadata_resolution.GROUPED_ANIME_PROVIDERS
    link_provider = target_source if wants_grouped else Sources.MAL.value

    converted = 0
    skipped = 0
    unresolved = []

    for item in anime_rows_needing_conversion(user):
        link = ItemProviderLink.objects.filter(
            item=item,
            provider=link_provider,
            provider_media_type=(
                MediaTypes.TV.value if wants_grouped else MediaTypes.ANIME.value
            ),
        ).first()
        if link is None:
            skipped += 1
            unresolved.append(item.title)
            continue

        try:
            library_migration.migrate_library_item(
                user,
                item,
                MediaTypes.ANIME.value,
                link_provider,
                link.provider_media_id,
            )
        except (
            AnimeMigrationError,
            LibraryMigrationError,
            ProviderAPIError,
        ) as error:
            skipped += 1
            unresolved.append(item.title)
            logger.warning("Left %r in its current shape: %s", item.title, error)
            continue
        except Exception:
            skipped += 1
            unresolved.append(item.title)
            logger.warning("Shape conversion crashed for %r", item.title, exc_info=True)
            continue

        converted += 1

    return {"converted": converted, "skipped": skipped, "unresolved": unresolved}
