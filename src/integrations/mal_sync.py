"""OAuth connection handling and status pushing for MyAnimeList sync.

MyAnimeList's OAuth2 implementation only supports the "plain" PKCE transform,
so the code_challenge sent to /authorize is the same string as the
code_verifier sent to /token (see
https://myanimelist.net/apiconfig/references/authorization). Because the
redirect URI must match exactly what's registered on MAL, a shared client
can't work the way MAL_API does for read-only search - each user or instance
needs their own MyAnimeList API application, brought through the same
Settings > Metadata credential system as everything else (see
app.providers.credentials, slug "mal").
"""

import logging
import secrets
from datetime import timedelta

import requests
from django.apps import apps
from django.db import transaction
from django.utils import timezone

from app.models.choices import MediaTypes, Sources, Status
from app.providers import credentials, services
from integrations.imports.helpers import decrypt, encrypt
from integrations.models import MALAccount

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://myanimelist.net/v1/oauth2/authorize"
TOKEN_URL = "https://myanimelist.net/v1/oauth2/token"  # noqa: S105 (URL, not a secret)
API_BASE_URL = "https://api.myanimelist.net/v2"

# Refresh slightly before the real expiry so a push never races an expiring token.
EXPIRY_LEEWAY = timedelta(minutes=2)

ANIME_STATUS_TO_MAL = {
    Status.COMPLETED.value: "completed",
    Status.IN_PROGRESS.value: "watching",
    Status.PLANNING.value: "plan_to_watch",
    Status.PAUSED.value: "on_hold",
    Status.DROPPED.value: "dropped",
}

MANGA_STATUS_TO_MAL = {
    Status.COMPLETED.value: "completed",
    Status.IN_PROGRESS.value: "reading",
    Status.PLANNING.value: "plan_to_read",
    Status.PAUSED.value: "on_hold",
    Status.DROPPED.value: "dropped",
}

# The field MAL accepts on a write differs from the field it reports back on a
# read (e.g. "num_watched_episodes" in, "num_episodes_watched" out).
PROGRESS_RESPONSE_FIELDS = {
    MediaTypes.ANIME.value: ("num_watched_episodes", "num_episodes_watched"),
    MediaTypes.MANGA.value: ("num_chapters_read", "num_chapters_read"),
}


class MALAuthError(Exception):
    """Raised when MyAnimeList rejects an OAuth request or credentials are missing."""


class MALSyncMismatchError(Exception):
    """Raised when MAL returns success but its response shows the change wasn't applied.

    Seen for some new list adds (HTTP 200, but the item never shows up on the
    user's MAL list) - MAL doesn't surface a clean error for this, so the only
    way to detect it is to check the echoed list_status against what was sent.
    """


def client_id(user):
    """Return the MAL client ID to use for this user (personal or shared)."""
    return credentials.get("mal", "client_id", user=user)


def client_secret(user):
    """Return the MAL client secret to use for this user (personal or shared)."""
    return credentials.get("mal", "client_secret", user=user)


def is_sync_configured(user):
    """Return whether this user has both MAL credentials needed for OAuth."""
    return bool(client_id(user) and client_secret(user))


def generate_code_verifier():
    """Return a PKCE code_verifier (also the code_challenge - see module docstring)."""
    return secrets.token_urlsafe(64)


def exchange_code_for_tokens(user, code, code_verifier, redirect_uri):
    """Exchange an authorization code for a fresh access/refresh token pair."""
    data = {
        "client_id": client_id(user),
        "client_secret": client_secret(user),
        "code": code,
        "code_verifier": code_verifier,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    return _request_token(user, data)


def _refresh_tokens(mal_account):
    """Use the stored refresh token to obtain a new token pair."""
    data = {
        "client_id": client_id(mal_account.user),
        "client_secret": client_secret(mal_account.user),
        "refresh_token": decrypt(mal_account.refresh_token),
        "grant_type": "refresh_token",
    }
    return _request_token(mal_account.user, data)


def _request_token(user, data):
    """POST to the MAL token endpoint and normalize auth failures.

    api_request() lets requests.exceptions.HTTPError propagate (after handling
    retries itself) rather than wrapping it - every caller normalizes its own
    errors, the same way app.providers.mal does for reads.
    """
    if not is_sync_configured(user):
        msg = (
            "MyAnimeList sync isn't configured. Add your own MyAnimeList Client "
            "ID and Client secret under Settings > Metadata."
        )
        raise MALAuthError(msg)

    try:
        return services.api_request(Sources.MAL.value, "POST", TOKEN_URL, data=data)
    except requests.exceptions.HTTPError as error:
        status_code = getattr(error.response, "status_code", None)
        if status_code in {requests.codes.unauthorized, requests.codes.bad_request}:
            msg = "MyAnimeList rejected the request. Please reconnect your account."
            raise MALAuthError(msg) from error
        raise services.ProviderAPIError(Sources.MAL.value, error) from error


def _store_tokens(mal_account, token_response):
    """Persist a fresh token pair on the account (refresh tokens are one-time use)."""
    mal_account.access_token = encrypt(token_response["access_token"])
    mal_account.refresh_token = encrypt(token_response["refresh_token"])
    mal_account.token_expires_at = timezone.now() + timedelta(
        seconds=token_response["expires_in"],
    )
    mal_account.save(
        update_fields=[
            "access_token",
            "refresh_token",
            "token_expires_at",
            "updated_at",
        ],
    )


def get_valid_access_token(mal_account):
    """Return a usable (decrypted) access token, refreshing it first if needed."""
    if timezone.now() >= mal_account.token_expires_at - EXPIRY_LEEWAY:
        with transaction.atomic():
            current = MALAccount.objects.select_for_update().select_related("user").get(pk=mal_account.pk)
            if timezone.now() >= current.token_expires_at - EXPIRY_LEEWAY:
                token_response = _refresh_tokens(current)
                _store_tokens(current, token_response)
            mal_account.access_token = current.access_token
            mal_account.refresh_token = current.refresh_token
            mal_account.token_expires_at = current.token_expires_at

    return decrypt(mal_account.access_token)


def fetch_username(user, access_token):
    """Look up the display name for the account behind an access token."""
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        response = services.api_request(
            Sources.MAL.value,
            "GET",
            f"{API_BASE_URL}/users/@me",
            params={"fields": "name"},
            headers=headers,
        )
    except requests.exceptions.HTTPError:
        logger.warning("Could not fetch the MyAnimeList username after connecting.")
        return ""
    return response.get("name", "")


def connect_account(user, code, code_verifier, redirect_uri):
    """Exchange an auth code and create or refresh the user's MAL connection."""
    token_response = exchange_code_for_tokens(user, code, code_verifier, redirect_uri)

    mal_account, _ = MALAccount.objects.get_or_create(
        user=user,
        defaults={
            "access_token": "",
            "refresh_token": "",
            "token_expires_at": timezone.now(),
        },
    )
    _store_tokens(mal_account, token_response)

    mal_account.mal_username = fetch_username(user, decrypt(mal_account.access_token))
    mal_account.sync_enabled = True
    mal_account.connection_broken = False
    mal_account.last_error_message = ""
    mal_account.save(
        update_fields=[
            "mal_username",
            "sync_enabled",
            "connection_broken",
            "last_error_message",
            "updated_at",
        ],
    )
    return mal_account


def status_payload(media):
    """Return the exact fields that Floppy will push for a media entry."""
    media_type = media.item.media_type
    is_anime = media_type == MediaTypes.ANIME.value
    status_map = ANIME_STATUS_TO_MAL if is_anime else MANGA_STATUS_TO_MAL
    progress_field = "num_watched_episodes" if is_anime else "num_chapters_read"

    data = {
        "status": status_map[media.status],
        progress_field: media.progress,
    }
    if media.score is not None:
        data["score"] = round(media.score)
    return data


def _resolve_mal_from_provider_link(provider, provider_media_id, season_number, episode_number):
    """Resolve an episode through Floppy's own exact migration/correction mapping.

    ItemProviderLink is written by Floppy itself (auto-migrating a completed
    flat MAL anime, or a manual match correction) with an exact season and
    episode offset - unlike AniBridge's external mapping data, it cannot be
    ambiguous for shows with recap or alternate-numbering episodes, so it is
    tried first.
    """
    from app.models import ItemProviderLink

    if not provider_media_id or season_number is None or episode_number is None:
        return None, None

    link = (
        ItemProviderLink.objects.filter(
            provider=provider,
            provider_media_type=MediaTypes.TV.value,
            provider_media_id=str(provider_media_id),
            season_number=season_number,
            item__source=Sources.MAL.value,
            item__media_type=MediaTypes.ANIME.value,
        )
        .select_related("item")
        .first()
    )
    if link is None:
        link = (
            ItemProviderLink.objects.filter(
                provider=provider,
                provider_media_type=MediaTypes.TV.value,
                provider_media_id=str(provider_media_id),
                season_number__isnull=True,
                item__source=Sources.MAL.value,
                item__media_type=MediaTypes.ANIME.value,
            )
            .select_related("item")
            .first()
        )
    if link is None:
        return None, None

    mapped_episode = episode_number - int(link.episode_offset or 0)
    if mapped_episode < 1:
        return None, None
    return str(link.item.media_id), mapped_episode


def queue_grouped_sync(user_id, item):
    """Queue current grouped progress after commit for connected, opted-in users."""
    from app.models import TV
    from integrations.tasks import sync_mal_status

    if item is None or item.library_media_type != MediaTypes.ANIME.value:
        return
    if not MALAccount.objects.filter(
        user_id=user_id,
        sync_enabled=True,
        per_item_sync_enabled=True,
        connection_broken=False,
    ).exists():
        return
    shows = TV.objects.filter(user_id=user_id, item__library_media_type="anime")
    if item.media_type == MediaTypes.TV.value:
        shows = shows.filter(item=item)
    elif item.media_type in {MediaTypes.SEASON.value, MediaTypes.EPISODE.value}:
        shows = shows.filter(
            seasons__item__source=item.source,
            seasons__item__media_id=item.media_id,
            seasons__item__season_number=item.season_number,
            seasons__order_archived=False,
        )
    else:
        return
    for show_id in shows.values_list("pk", flat=True).distinct():
        transaction.on_commit(
            lambda show_id=show_id: sync_mal_status.delay(
                media_type="tv", media_id=show_id,
            ),
        )


def grouped_sync_entries(user, tv=None, mapping_issues=None, progress_callback=None):
    """Project grouped anime watches into transient MAL entries, one per cour."""
    from app.models import TV, Anime, Episode, Item, WatchState
    from integrations.models import ExternalReference
    from integrations.webhooks import anime_mappings

    shows = TV.objects.filter(
        user=user, item__library_media_type=MediaTypes.ANIME.value,
    )
    if tv is not None:
        shows = shows.filter(pk=tv.pk)
    shows = list(shows.select_related("item", "active_episode_order"))
    if not shows:
        return []

    mapping_data = anime_mappings.fetch_mapping_data()
    manual_mappings = {
        reference.external_identity: reference.episode_mapping
        for reference in ExternalReference.objects.filter(
            user=user,
            integration="mal_sync",
            external_namespace="grouped_anime_episode",
            review_status="corrected",
        )
    }
    entries = {}
    for show_index, show in enumerate(shows, start=1):
        if progress_callback:
            progress_callback(show_index, len(shows), show.item.title)
        unmapped = []
        unmapped_episodes = []
        season_counts = {}
        watches = Episode.objects.filter(
            related_season__related_tv=show,
            related_season__order_archived=False,
        ).select_related("item", "related_season")
        states = WatchState.objects.filter(
            user=user,
            item__media_type=MediaTypes.EPISODE.value,
            item__library_media_type=MediaTypes.ANIME.value,
            item__source=show.tracking_source,
            item__media_id=show.tracking_media_id,
        ).select_related("item")
        coordinates = {
            state.item_id: (state.item, False, show.score)
            for state in states
        }
        for watch in watches:
            if watch.item_id is None:
                continue
            previous = coordinates.get(watch.item_id)
            watched = not watch.dropped or bool(previous and previous[1])
            score = watch.related_season.score
            coordinates[watch.item_id] = (
                watch.item,
                watched,
                score if score is not None else show.score,
            )

        for item, watched, score in coordinates.values():
            if item.season_number is None or item.episode_number is None:
                unmapped.append(item.title)
                continue
            season_count = season_counts.setdefault(
                item.season_number,
                {"total": 0, "unmapped": []},
            )
            season_count["total"] += 1
            identity = f"{show.item_id}:{item.season_number}:{item.episode_number}"
            manual = manual_mappings.get(identity, {})
            mal_id = manual.get("mal_id")
            episode_number = manual.get("episode")
            if not mal_id or not episode_number:
                mal_id, episode_number = _resolve_mal_from_provider_link(
                    item.source,
                    item.media_id,
                    item.season_number,
                    item.episode_number,
                )
            if not mal_id or not episode_number:
                mal_id, episode_number = anime_mappings.get_mal_id_from_series(
                    mapping_data,
                    item.source,
                    item.media_id,
                    item.season_number,
                    item.episode_number,
                )
            if not mal_id or not episode_number or episode_number < 1:
                unmapped.append(f"S{item.season_number:02}E{item.episode_number:02}")
                unmapped_episodes.append({
                    "season": item.season_number,
                    "episode": item.episode_number,
                })
                season_count["unmapped"].append(item.episode_number)
                continue
            mal_id = str(mal_id)
            if mal_id not in entries:
                with credentials.current_user_scope(user):
                    metadata = services.get_media_metadata(
                        "anime", mal_id, Sources.MAL.value,
                    )
                entries[mal_id] = (
                    Anime(
                        user=user,
                        item=Item(
                            media_id=mal_id,
                            source=Sources.MAL.value,
                            media_type=MediaTypes.ANIME.value,
                            title=metadata["title"],
                        ),
                        score=score,
                        status=show.status,
                        progress=0,
                    ),
                    set(),
                    metadata.get("max_progress"),
                )
            _, watched_numbers, _ = entries[mal_id]
            if watched:
                watched_numbers.add(episode_number)

        if mapping_issues is not None and (unmapped or not coordinates):
            mapping_issues.append({
                "title": show.item.title,
                "media_type": "Anime",
                "mal_id": "",
                "item_id": show.item_id,
                "episodes": unmapped_episodes,
                "seasons": [
                    {
                        "season": season,
                        "episodes": sorted(values["unmapped"]),
                        "all_unmapped": bool(values["unmapped"])
                        and len(values["unmapped"]) == values["total"],
                    }
                    for season, values in sorted(season_counts.items())
                    if values["unmapped"]
                ],
                "outcome": "skipped",
                "reason": (
                    "No reliable MAL episode mapping for: " + ", ".join(sorted(set(unmapped)))
                    if unmapped else "No episode history available to resolve a MAL mapping."
                ),
            })

    result = []
    for media, watched_numbers, total in entries.values():
        media.progress = len(watched_numbers)
        if total and media.progress >= total:
            media.status = Status.COMPLETED.value
        elif media.status not in {Status.DROPPED.value, Status.PAUSED.value}:
            media.status = (
                Status.IN_PROGRESS.value if media.progress else Status.PLANNING.value
            )
        result.append(media)
    return result


def full_sync_entries(
    user, mal_account=None, mapping_issues=None, progress_callback=None,
):
    """Return every MAL-backed anime/manga entry eligible for a full sync.

    Applies the account's sync filters (which statuses to include, and
    whether to require a score) when a MALAccount is given. The automatic
    per-item push in integrations.tasks._mal_sync.sync_mal_status bypasses
    these filters and always pushes whatever a saved entry's status is.
    """
    Anime = apps.get_model(app_label="app", model_name="anime")  # noqa: N806
    Manga = apps.get_model(app_label="app", model_name="manga")  # noqa: N806

    included_statuses = set()
    if mal_account is None or mal_account.sync_filter_watched:
        included_statuses.update({Status.COMPLETED.value, Status.IN_PROGRESS.value})
    if mal_account is None or mal_account.sync_filter_dropped:
        included_statuses.add(Status.DROPPED.value)

    filters = {
        "user": user,
        "item__source": Sources.MAL.value,
        "status__in": included_statuses,
    }
    entries = [
        *Anime.objects.filter(**filters).select_related("item"),
        *Manga.objects.filter(**filters).select_related("item"),
        *[
            media for media in grouped_sync_entries(
                user,
                mapping_issues=mapping_issues,
                progress_callback=progress_callback,
            )
            if media.status in included_statuses
        ],
    ]
    entries = list({
        (media.item.media_type, media.item.media_id): media for media in entries
    }.values())
    if mal_account is not None and mal_account.sync_filter_rated_only:
        entries = [media for media in entries if media.score is not None]
    return entries


def _fetch_list_statuses(media_type, mal_account):
    """Return MAL list statuses keyed by media ID for one media type."""
    access_token = get_valid_access_token(mal_account)
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"fields": "list_status", "limit": 1000, "nsfw": "true"}
    url = f"{API_BASE_URL}/users/@me/{media_type}list"
    statuses = {}

    while url:
        try:
            response = services.api_request(
                Sources.MAL.value,
                "GET",
                url,
                params=params,
                headers=headers,
            )
        except requests.exceptions.HTTPError as error:
            status_code = getattr(error.response, "status_code", None)
            if status_code in {
                requests.codes.unauthorized,
                requests.codes.forbidden,
            }:
                msg = "MyAnimeList rejected the request. Please reconnect your account."
                raise MALAuthError(msg) from error
            raise services.ProviderAPIError(Sources.MAL.value, error) from error

        for entry in response.get("data", []):
            statuses[str(entry["node"]["id"])] = entry.get("list_status", {})
        url = response.get("paging", {}).get("next")
        params = None

    return statuses


def full_sync_report(mal_account):
    """Return the persisted report used by both page loads and live polling."""
    return {
        "status": mal_account.full_sync_status,
        "status_label": mal_account.get_full_sync_status_display(),
        "is_active": mal_account.full_sync_is_active,
        "total": mal_account.full_sync_total,
        "processed": mal_account.full_sync_processed,
        "succeeded": mal_account.full_sync_succeeded,
        "failed": mal_account.full_sync_failed,
        "results": mal_account.full_sync_results,
        "mapping_issues": [
            result for result in mal_account.full_sync_results
            if result.get("outcome") == "skipped"
        ],
        "started_at": mal_account.full_sync_started_at,
        "completed_at": mal_account.full_sync_completed_at,
    }


def preview_full_sync(user, mal_account, mapping_issues=None, progress_callback=None):
    """Return field-level changes a full sync would make without writing to MAL."""
    if progress_callback:
        progress_callback(5, "Loading your MyAnimeList anime list")
    remote_statuses = {
        MediaTypes.ANIME.value: _fetch_list_statuses(MediaTypes.ANIME.value, mal_account),
    }
    if progress_callback:
        progress_callback(20, "Loading your MyAnimeList manga list")
    remote_statuses[MediaTypes.MANGA.value] = _fetch_list_statuses(
        MediaTypes.MANGA.value, mal_account,
    )
    field_labels = {
        "status": "Status",
        "num_watched_episodes": "Episodes watched",
        "num_chapters_read": "Chapters read",
        "score": "Score",
    }
    preview = []

    def grouped_progress(current, total, title):
        if progress_callback:
            progress_callback(
                30 + round(current / max(total, 1) * 55),
                f"Checking anime mappings: {title}",
            )

    entries = full_sync_entries(
        user,
        mal_account,
        mapping_issues=mapping_issues,
        progress_callback=grouped_progress,
    )
    if progress_callback:
        progress_callback(90, "Comparing local and MyAnimeList entries")
    for media in entries:
        media_type = media.item.media_type
        desired = status_payload(media)
        current = remote_statuses[media_type].get(str(media.item.media_id))
        changes = []
        for field, new_value in desired.items():
            remote_field = (
                PROGRESS_RESPONSE_FIELDS[media_type][1]
                if field == PROGRESS_RESPONSE_FIELDS[media_type][0]
                else field
            )
            old_value = current.get(remote_field) if current is not None else None
            if old_value != new_value:
                changes.append(
                    {
                        "field": field_labels[field],
                        "from": old_value,
                        "to": new_value,
                    }
                )

        if changes:
            preview.append(
                {
                    "title": media.item.title,
                    "media_type": media_type.title(),
                    "mal_id": str(media.item.media_id),
                    "not_on_list": current is None,
                    "changes": changes,
                }
            )

    if progress_callback:
        progress_callback(100, "Preview ready")
    return preview


def push_status(media, mal_account):
    """Push a MAL-backed Anime/Manga entry's status, progress and score to MAL.

    Args:
        media: A saved Anime or Manga instance whose item.source is MAL.
        mal_account: The user's MALAccount to push through.
    """
    media_type = media.item.media_type
    data = status_payload(media)

    access_token = get_valid_access_token(mal_account)
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{API_BASE_URL}/{media_type}/{media.item.media_id}/my_list_status"

    try:
        response = services.api_request(
            Sources.MAL.value,
            "PUT",
            url,
            data=data,
            headers=headers,
        )
    except requests.exceptions.HTTPError as error:
        status_code = getattr(error.response, "status_code", None)
        if status_code in {requests.codes.unauthorized, requests.codes.forbidden}:
            msg = "MyAnimeList rejected the request. Please reconnect your account."
            raise MALAuthError(msg) from error
        raise services.ProviderAPIError(Sources.MAL.value, error) from error

    sent_field, response_field = PROGRESS_RESPONSE_FIELDS[media_type]
    mismatches = [
        field
        for field, value in data.items()
        if response.get(response_field if field == sent_field else field) != value
    ]
    if mismatches:
        msg = (
            f"MyAnimeList accepted the update for {media.item.title} (MAL ID "
            f"{media.item.media_id}) but its response shows it wasn't applied "
            f"({', '.join(mismatches)})."
        )
        raise MALSyncMismatchError(msg)

    logger.info(
        "Synced %s (MAL ID %s) to MyAnimeList for user %s",
        media.item.title,
        media.item.media_id,
        mal_account.user,
    )
