"""Resolve a game's logo and backdrop from the best provider for each.

IGDB stays Floppy's game metadata source and the backdrop fallback. This
package looks for something better first, and the two assets are resolved
independently, so a game can end up with a SteamGridDB logo and a ScreenScraper
backdrop. The result is stored with its provider, so a later "refresh" or "pick
another" does not need a new data model.

Which providers are asked, and in what order, depends on what Floppy knows:

* a Steam AppID: Steam, SteamGridDB, TheGamesDB (and ScreenScraper for retro)
* a retro platform: ScreenScraper, TheGamesDB, SteamGridDB, Libretro
* anything else: SteamGridDB, TheGamesDB

See ``docs/architecture/game-artwork.md``.
"""

import logging
import time
from datetime import UTC, datetime, timedelta

from django.core.cache import cache
from django.db import IntegrityError
from django.utils import timezone

from app.game_artwork import (
    libretro,
    screenscraper,
    steam,
    steamgriddb,
    thegamesdb,
)
from app.game_artwork.base import BACKDROP, LOGO, Art, GameQuery
from app.models import GameArtwork, Sources
from app.providers import credentials

logger = logging.getLogger(__name__)

# Time budget for one resolution, checked between providers.
RESOLVE_BUDGET_SECONDS = 12
# A game with both assets from a real provider is left alone this long; one with
# a gap is tried again sooner, since a key may have been added since.
COMPLETE_TTL = timedelta(days=30)
INCOMPLETE_TTL = timedelta(hours=6)
# After a provider error nothing is stored; this stops every page view retrying.
ERROR_BACKOFF_SECONDS = 300
IGDB_PROVIDER = "igdb"
MAX_URL_LENGTH = GameArtwork._meta.get_field("logo_url").max_length


def query_for(media_id, metadata):
    """Build the lookup from a game's IGDB metadata (``igdb.game``)."""
    details = metadata.get("details") or {}
    release_date = str(details.get("release_date") or "")
    year = int(release_date[:4]) if release_date[:4].isdigit() else None
    return GameQuery(
        media_id=str(media_id),
        title=metadata.get("title") or "",
        platforms=tuple(details.get("platforms") or ()),
        year=year,
        steam_app_id=(metadata.get("external_ids") or {}).get("steam_app_id", ""),
    )


def provider_order(query):
    """Return the provider modules to ask for this game, best first."""
    if query.steam_app_id:
        order = [steam, steamgriddb, thegamesdb]
        if query.systems:
            order.append(screenscraper)
        return order
    if query.systems:
        return [screenscraper, thegamesdb, steamgriddb, libretro]
    return [steamgriddb, thegamesdb]


# Providers whose credentials decide what a lookup can find.
CREDENTIAL_PROVIDERS = frozenset(
    provider.PROVIDER for provider in (screenscraper, steamgriddb, thegamesdb)
)
_DUE_NOW = datetime(1970, 1, 1, tzinfo=UTC)


def _keys_changed_cache_key(scope):
    return f"game_artwork_keys_changed_{scope}"


def keys_saved(user=None):
    """Note that an artwork provider key was saved, for one member or the instance.

    Rows with a gap are then looked up again, but only by a request the key
    applies to: a member without the key would otherwise search, find nothing and
    settle the row before the member who added it ever visits.
    """
    scope = user.pk if user is not None else "instance"
    cache.set(_keys_changed_cache_key(scope), time.time(), None)


def _keys_changed_at():
    """Return when a key that applies to the current request was last saved."""
    user = credentials.active_user()
    scopes = ["instance", *([user.pk] if user is not None else [])]
    return max(cache.get(_keys_changed_cache_key(scope)) or 0 for scope in scopes)


def _error_key(media_id):
    # Saving a key changes the key, so an earlier outage does not delay its first try.
    return f"game_artwork_error_{media_id}_{_keys_changed_at()}"


def _search(query):
    """Ask providers in order for whichever assets are still missing.

    Returns ``(found, errored)``. One failing provider never stops the others.
    """
    found = {}
    errored = False
    started = time.monotonic()
    for provider in provider_order(query):
        wanted = [kind for kind in (LOGO, BACKDROP) if kind not in found]
        if not wanted:
            break
        if time.monotonic() - started > RESOLVE_BUDGET_SECONDS:
            errored = True
            break
        try:
            # A URL the column cannot hold would fail the save for every asset
            # of the game, so such an image is treated as not found.
            found.update(
                {
                    kind: art
                    for kind, art in provider.find(query, wanted).items()
                    if art.url and len(art.url) <= MAX_URL_LENGTH
                },
            )
        except Exception:
            errored = True
            logger.warning(
                "Game artwork lookup failed for %s (%s)",
                query.title,
                provider.PROVIDER,
                exc_info=True,
            )
    return found, errored


def is_stale(row):
    """Return whether a stored row is due to be looked up again."""
    complete = bool(row.logo_url) and row.backdrop_provider not in ("", IGDB_PROVIDER)
    ttl = COMPLETE_TTL if complete else INCOMPLETE_TTL
    if timezone.now() - row.resolved_at > ttl:
        return True
    return not complete and row.resolved_at.timestamp() < _keys_changed_at()


def expire(media_id):
    """Make a game's stored artwork due for a new lookup on its next page view.

    Used by a manual metadata refresh. The stored assets stay in place: a lookup
    that finds nothing keeps them.
    """
    cache.delete(_error_key(media_id))
    # update() skips auto_now, so resolved_at really becomes the old date.
    GameArtwork.objects.filter(
        source=Sources.IGDB.value,
        media_id=str(media_id),
    ).update(resolved_at=_DUE_NOW)


def _art(row, kind):
    url = getattr(row, f"{kind}_url")
    if not url:
        return None
    return Art(
        url,
        getattr(row, f"{kind}_provider"),
        getattr(row, f"{kind}_provider_id"),
    )


def peek(media_id):
    """Read fresh stored artwork without triggering a provider lookup."""
    row = GameArtwork.objects.filter(
        source=Sources.IGDB.value,
        media_id=str(media_id),
    ).first()
    if row is None or is_stale(row):
        return None
    return {"logo": _art(row, "logo"), "backdrop": _art(row, "backdrop")}


def resolve(query, *, fallback_backdrop=None):
    """Return ``{"logo": Art | None, "backdrop": Art | None}`` for a game.

    ``fallback_backdrop`` is IGDB's own artwork, used (and recorded as such)
    when no artwork provider has a backdrop.
    """
    row = GameArtwork.objects.filter(
        source=Sources.IGDB.value,
        media_id=query.media_id,
    ).first()
    # During an error backoff nothing is searched and nothing stored: storing
    # would record an outage's empty result and settle the row for hours.
    if (row is None or is_stale(row)) and not cache.get(_error_key(query.media_id)):
        found, errored = _search(query)
        if errored and not found:
            cache.set(_error_key(query.media_id), 1, ERROR_BACKOFF_SECONDS)
        if found or not errored:
            row = _store(query, found, fallback_backdrop, existing=row)
    logo = _art(row, LOGO) if row else None
    backdrop = _art(row, BACKDROP) if row else None
    if backdrop is None or backdrop.provider == IGDB_PROVIDER:
        # IGDB's own artwork is read fresh rather than from the stored copy.
        backdrop = fallback_backdrop or backdrop
    return {LOGO: logo, BACKDROP: backdrop}


def _store(query, found, fallback_backdrop, *, existing):
    """Save what was found, keeping an earlier asset a failed search missed."""
    values = {}
    for kind in (LOGO, BACKDROP):
        art = found.get(kind)
        if art is None and kind == BACKDROP:
            art = fallback_backdrop
        if art is None and existing is not None:
            art = _art(existing, kind)
        values[f"{kind}_url"] = art.url if art else ""
        values[f"{kind}_provider"] = art.provider if art else ""
        values[f"{kind}_provider_id"] = art.provider_id if art else ""
    try:
        row, _ = GameArtwork.objects.update_or_create(
            source=Sources.IGDB.value,
            media_id=query.media_id,
            defaults=values,
        )
    except IntegrityError:
        # A concurrent request stored the same game first; theirs is as good.
        row = GameArtwork.objects.get(
            source=Sources.IGDB.value,
            media_id=query.media_id,
        )
    return row
