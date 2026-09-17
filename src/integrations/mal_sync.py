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
        token_response = _refresh_tokens(mal_account)
        _store_tokens(mal_account, token_response)

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


def full_sync_entries(user):
    """Return every MAL-backed anime/manga entry eligible for a full sync."""
    Anime = apps.get_model(app_label="app", model_name="anime")  # noqa: N806
    Manga = apps.get_model(app_label="app", model_name="manga")  # noqa: N806
    filters = {
        "user": user,
        "item__source": Sources.MAL.value,
        "status__isnull": False,
    }
    return [
        *Anime.all_objects.filter(**filters).select_related("item"),
        *Manga.objects.filter(**filters).select_related("item"),
    ]


def _fetch_list_statuses(media_type, mal_account):
    """Return MAL list statuses keyed by media ID for one media type."""
    access_token = get_valid_access_token(mal_account)
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"fields": "list_status", "limit": 1000}
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


def preview_full_sync(user, mal_account):
    """Return field-level changes a full sync would make without writing to MAL."""
    remote_statuses = {
        media_type: _fetch_list_statuses(media_type, mal_account)
        for media_type in (MediaTypes.ANIME.value, MediaTypes.MANGA.value)
    }
    field_labels = {
        "status": "Status",
        "num_watched_episodes": "Episodes watched",
        "num_chapters_read": "Chapters read",
        "score": "Score",
    }
    preview = []

    for media in full_sync_entries(user):
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
