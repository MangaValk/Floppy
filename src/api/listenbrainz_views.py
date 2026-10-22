# FORK: ListenBrainz-compatible ingest endpoints. Mounted at the root under
# /apis/listenbrainz/1/ rather than /api/v1/ so that any client accepting a
# custom ListenBrainz URL (Multi-Scrobbler, Navidrome, Pano Scrobbler, ...) can
# point at Floppy's base URL unmodified. Receive-only: Floppy never submits
# listens outward. URL wiring lives in listenbrainz_urls.py.
import logging
from datetime import UTC, datetime
from http import HTTPStatus as HTTP  # noqa: N814

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import views as drf_views
from rest_framework.response import Response

from api.authentication import ListenBrainzTokenAuthentication
from api.contract_serializers import (
    DetailErrorSerializer,
    ListenBrainzErrorSerializer,
    ListenBrainzListensSerializer,
    ListenBrainzStatusSerializer,
    ListenBrainzTokenSerializer,
)
from app.models import Music
from integrations.webhooks.listenbrainz import ListenBrainzScrobbleProcessor

logger = logging.getLogger(__name__)

# "single" and "import" are recorded; "playing_now" is accepted but not stored.
_RECORDED_LISTEN_TYPES = ("single", "import")
_LISTEN_TYPES = (*_RECORDED_LISTEN_TYPES, "playing_now")

MAX_LISTENS_PER_SUBMISSION = 1000
DEFAULT_LISTENS_PAGE_SIZE = 25
MAX_LISTENS_PAGE_SIZE = 1000


def _error(message, status=HTTP.BAD_REQUEST):
    """Return a ListenBrainz-shaped error response."""
    return Response({"code": int(status), "error": message}, status=status)


def _optional_int(params, name):
    """Return an integer query parameter, or None when it is absent."""
    raw = params.get(name)
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _listen_metadata(music, origin_url):
    """Build the track metadata for one historical play."""
    track = music.track
    album = music.album
    artist = music.artist or (album.artist if album else None)

    track_name = track.title if track else music.item.title
    metadata = {
        "artist_name": artist.name if artist else "",
        "track_name": track_name,
    }
    if album:
        metadata["release_name"] = album.title

    additional = {}
    if track and track.musicbrainz_recording_id:
        additional["recording_mbid"] = track.musicbrainz_recording_id
    if album and album.musicbrainz_release_id:
        additional["release_mbid"] = album.musicbrainz_release_id
    if album and album.musicbrainz_release_group_id:
        additional["release_group_mbid"] = album.musicbrainz_release_group_id
    if artist and artist.musicbrainz_id:
        additional["artist_mbids"] = [artist.musicbrainz_id]
    if track and track.duration_ms:
        additional["duration_ms"] = track.duration_ms
    if track and track.track_number:
        additional["tracknumber"] = track.track_number
    if origin_url:
        additional["origin_url"] = origin_url
    if additional:
        metadata["additional_info"] = additional
    return metadata


@extend_schema_view(
    get=extend_schema(
        operation_id="getListenBrainzUserListens",
        summary="Get listens for a user (ListenBrainz-compatible)",
        description=(
            "Returns recorded plays newest first, so ListenBrainz clients such as "
            "Multi-Scrobbler can check what has already reached Floppy before "
            "submitting a play. Only the token owner's listens are available."
        ),
        parameters=[
            OpenApiParameter(
                name="username",
                type=str,
                location=OpenApiParameter.PATH,
                description="The token owner's Floppy username.",
            ),
            OpenApiParameter(
                name="count",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Maximum listens to return (default 25).",
            ),
            OpenApiParameter(
                name="min_ts",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Exclusive lower bound on listened_at (Unix seconds).",
            ),
            OpenApiParameter(
                name="max_ts",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Exclusive upper bound on listened_at (Unix seconds).",
            ),
        ],
        responses={
            200: ListenBrainzListensSerializer,
            400: ListenBrainzErrorSerializer,
            401: DetailErrorSerializer,
            404: ListenBrainzErrorSerializer,
        },
    )
)
class UserListensView(drf_views.APIView):
    """ListenBrainz `user/<username>/listens` endpoint."""

    authentication_classes = [ListenBrainzTokenAuthentication]

    def get(self, request, username):
        """Return the token owner's plays in the requested time window."""
        if username.lower() != request.user.username.lower():
            return _error("User not found.", status=HTTP.NOT_FOUND)

        count = _optional_int(request.query_params, "count")
        if count is None:
            count = DEFAULT_LISTENS_PAGE_SIZE
        if count < 1:
            return _error("count must be a positive integer.")
        count = min(count, MAX_LISTENS_PAGE_SIZE)

        min_ts = _optional_int(request.query_params, "min_ts")
        max_ts = _optional_int(request.query_params, "max_ts")
        for name, value in (("min_ts", min_ts), ("max_ts", max_ts)):
            if request.query_params.get(name) not in (None, "") and value is None:
                return _error(f"{name} must be an integer Unix timestamp.")

        history_model = Music.history.model
        rows = history_model.objects.filter(
            id__in=Music.objects.filter(user=request.user).values("id"),
            end_date__isnull=False,
        )
        if min_ts is not None:
            rows = rows.filter(
                end_date__gt=datetime.fromtimestamp(min_ts, tz=UTC),
            )
        if max_ts is not None:
            rows = rows.filter(
                end_date__lt=datetime.fromtimestamp(max_ts, tz=UTC),
            )

        plays = []
        seen = set()
        for row in rows.order_by("-end_date", "-history_id").iterator():
            key = (row.id, row.end_date)
            if key in seen:
                continue
            seen.add(key)
            plays.append(row)
            if len(plays) >= count:
                break

        music_by_id = Music.objects.filter(
            user=request.user,
            id__in={row.id for row in plays},
        ).select_related("item", "artist", "album", "track")
        music_by_id = {music.id: music for music in music_by_id}

        listens = []
        for row in plays:
            music = music_by_id.get(row.id)
            if music is None:
                continue
            listened_at = int(row.end_date.timestamp())
            listens.append(
                {
                    "listened_at": listened_at,
                    "track_metadata": _listen_metadata(
                        music,
                        row.origin_url or music.origin_url,
                    ),
                }
            )

        timestamps = [listen["listened_at"] for listen in listens]
        return Response(
            {
                "payload": {
                    "count": len(listens),
                    "listens": listens,
                    "latest_listen_ts": max(timestamps, default=0),
                    "oldest_listen_ts": min(timestamps, default=0),
                },
            },
            status=HTTP.OK,
        )


@extend_schema_view(
    post=extend_schema(
        operation_id="submitListenBrainzListens",
        summary="Submit listens (ListenBrainz-compatible)",
        description=(
            "Accepts scrobbles from any ListenBrainz-compatible client. "
            "Authenticate with `Authorization: Token <your API token>`. "
            "`playing_now` submissions are accepted but not recorded."
        ),
        request={
            "application/json": {
                "type": "object",
                "required": ["listen_type", "payload"],
                "properties": {
                    "listen_type": {
                        "type": "string",
                        "enum": list(_LISTEN_TYPES),
                    },
                    "payload": {"type": "array", "items": {"type": "object"}},
                },
            },
        },
        responses={
            200: ListenBrainzStatusSerializer,
            400: ListenBrainzErrorSerializer,
            401: DetailErrorSerializer,
            403: ListenBrainzErrorSerializer,
        },
    )
)
class SubmitListensView(drf_views.APIView):
    """ListenBrainz `submit-listens` endpoint."""

    authentication_classes = [ListenBrainzTokenAuthentication]

    def post(self, request):
        """Validate a submission and record its listens."""
        data = request.data
        if not isinstance(data, dict):
            return _error("JSON document must be a single object.")

        listen_type = data.get("listen_type")
        if listen_type not in _LISTEN_TYPES:
            return _error(
                f"Invalid listen_type. Must be one of: {', '.join(_LISTEN_TYPES)}.",
            )

        payload = data.get("payload")
        if not isinstance(payload, list):
            return _error("JSON document must contain a 'payload' list.")

        if len(payload) > MAX_LISTENS_PER_SUBMISSION:
            return _error(
                f"Too many listens in one submission "
                f"(maximum {MAX_LISTENS_PER_SUBMISSION}).",
            )

        if listen_type == "single" and len(payload) != 1:
            return _error(
                "Submission of type 'single' must contain exactly one listen."
            )

        # Accept and drop now-playing pings: recording one would mean creating
        # catalog rows for a track the user may never finish.
        if listen_type == "playing_now":
            return Response({"status": "ok"}, status=HTTP.OK)

        if not getattr(request.user, "music_enabled", False):
            return _error(
                "Music tracking is disabled for this account.",
                status=HTTP.FORBIDDEN,
            )

        if not payload:
            return Response({"status": "ok"}, status=HTTP.OK)

        stats = ListenBrainzScrobbleProcessor().process_listens(payload, request.user)
        self._refresh_statistics(request.user, stats["affected_day_keys"])

        logger.info(
            "ListenBrainz submission for %s: processed=%s skipped=%s errors=%s",
            request.user.username,
            stats["processed"],
            stats["skipped"],
            stats["errors"],
        )
        return Response({"status": "ok"}, status=HTTP.OK)

    def _refresh_statistics(self, user, day_keys):
        """Invalidate cached statistics for the affected days."""
        if not day_keys:
            return
        try:
            from app import statistics_cache

            statistics_cache.invalidate_statistics_days(
                user.id,
                day_values=list(day_keys),
                reason="listenbrainz_submission",
            )
            statistics_cache.schedule_all_ranges_refresh(user.id)
        except Exception:
            logger.exception(
                "Failed to refresh statistics after ListenBrainz submission"
            )


@extend_schema_view(
    get=extend_schema(
        operation_id="validateListenBrainzToken",
        summary="Validate token (ListenBrainz-compatible)",
        description=(
            "Reports whether the supplied token is valid. ListenBrainz clients call "
            "this on startup to confirm the connection."
        ),
        responses={200: ListenBrainzTokenSerializer, 401: DetailErrorSerializer},
    )
)
class ValidateTokenView(drf_views.APIView):
    """ListenBrainz `validate-token` endpoint."""

    authentication_classes = [ListenBrainzTokenAuthentication]

    def get(self, request):
        """Confirm the presented token is valid."""
        return Response(
            {
                "code": int(HTTP.OK),
                "message": "Token valid.",
                "valid": True,
                "user_name": request.user.username,
            },
            status=HTTP.OK,
        )
