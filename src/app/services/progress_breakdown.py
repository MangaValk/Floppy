"""Per-season, per-episode breakdown of how much of a show the user has watched.

The result is plain data so the same component can render one show in a modal
today and a row per show on a library progress page later.

Watched means finished at least once, in any pass. While a rewatch is open the
breakdown also reports how much of the current pass is done, using the same
pass-aware numbers as the progress card. The episode list comes from the
provider catalogue. An episode only counts toward a total once it has aired,
and specials and dropped seasons stay out of the overall figures, matching the
card's percentage.
"""

import json
import logging
from dataclasses import dataclass, field

from django.utils import timezone

from app.models import Season, Status
from app.providers import services
from app.services.bulk_episode_tracking import coerce_episode_datetime
from app.templatetags.app_tags import media_url

logger = logging.getLogger(__name__)

WATCHED = "watched"
UNWATCHED = "unwatched"
UPCOMING = "upcoming"


@dataclass
class SeasonProgress:
    """One season's episodes and totals."""

    number: int
    title: str
    url: str
    dropped: bool = False
    rewatching: bool = False
    catalogue_missing: bool = False
    episodes: list = field(default_factory=list)

    @property
    def counted(self):
        """Return the episodes that count toward totals (aired or watched)."""
        return [ep for ep in self.episodes if ep["state"] != UPCOMING]

    @property
    def total(self):
        """Return how many episodes count toward this season's total."""
        return len(self.counted)

    @property
    def watched(self):
        """Return how many episodes of the season are watched."""
        return sum(ep["state"] == WATCHED for ep in self.episodes)

    @property
    def percent(self):
        """Return the watched percentage, or None when nothing has aired."""
        if self.catalogue_missing or not self.total:
            return None
        return round(self.watched / self.total * 100)

    @property
    def rewatch_watched(self):
        """Return how many watched episodes are also done in the current pass."""
        return sum(ep["state"] == WATCHED and ep["rewatched"] for ep in self.episodes)

    @property
    def rewatch_percent(self):
        """Return the current pass's percentage while rewatching, else None."""
        if self.percent is None or not self.rewatching:
            return None
        return round(self.rewatch_watched / self.total * 100)

    @property
    def is_specials(self):
        """Return whether this is the specials season."""
        return self.number == 0

    @property
    def counts_toward_overall(self):
        """Return whether the season feeds the show's overall figures."""
        return not self.is_specials and not self.dropped and not self.catalogue_missing

    @property
    def minutes_left(self):
        """Return unwatched runtime in minutes, or None if any runtime is unknown."""
        left = [ep for ep in self.counted if ep["state"] == UNWATCHED]
        if any(not ep["runtime"] for ep in left):
            return None
        return sum(ep["runtime"] for ep in left)


@dataclass
class ProgressBreakdown:
    """A show (or one season) with its seasons and overall totals."""

    title: str
    seasons: list
    catalogue_unavailable: bool = False
    single_season: bool = False

    @property
    def overall(self):
        """Return the seasons that feed the overall figures."""
        if self.single_season:
            return [season for season in self.seasons if not season.catalogue_missing]
        return [season for season in self.seasons if season.counts_toward_overall]

    @property
    def total(self):
        """Return the overall episode total."""
        return sum(season.total for season in self.overall)

    @property
    def watched(self):
        """Return the overall watched count."""
        return sum(season.watched for season in self.overall)

    @property
    def rewatching(self):
        """Return whether any season feeding the overall figures is in a rewatch."""
        return any(season.rewatching for season in self.overall)

    @property
    def rewatch_watched(self):
        """Return the overall count finished in an open pass, over rewatching seasons only."""
        return sum(
            season.rewatch_watched for season in self.overall if season.rewatching
        )

    @property
    def rewatch_percent(self):
        """Return the overall current-pass percentage while rewatching, else None."""
        if not self.rewatching or not self.total:
            return None
        return round(self.rewatch_watched / self.total * 100)

    @property
    def left(self):
        """Return how many aired episodes are still unwatched."""
        return self.total - self.watched

    @property
    def percent(self):
        """Return the overall watched percentage, or None."""
        return round(self.watched / self.total * 100) if self.total else None

    @property
    def minutes_left(self):
        """Return overall unwatched runtime, or None if any runtime is unknown."""
        parts = [season.minutes_left for season in self.overall]
        if any(part is None for part in parts):
            return None
        return sum(parts)

    @property
    def minutes_left_label(self):
        """Return the unwatched runtime as text, or "" when it is not known."""
        minutes = self.minutes_left
        return format_minutes(minutes) if minutes else ""

    @property
    def open_state_json(self):
        """Return which season rows start expanded, keyed for the template's Alpine state."""
        opened = self.first_open_season
        return json.dumps(
            {
                f"s{season.number}": self.single_season or season.number == opened
                for season in self.seasons
            },
        )

    @property
    def first_open_season(self):
        """Return the number of the first season with something left to watch."""
        for season in self.seasons:
            if season.counts_toward_overall and season.watched < season.total:
                return season.number
        return None


def format_minutes(minutes):
    """Return minutes as "1h 25m" (or "40m")."""
    hours, rest = divmod(minutes, 60)
    return f"{hours}h {rest}m" if hours else f"{rest}m"


def _runtime_minutes(value):
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def _season_payloads(media_id, source, season_numbers):
    """Return {season_number: provider payload}, or {} when the provider fails."""
    try:
        with services.interactive_request_scope():
            if season_numbers is None:
                base = services.get_media_metadata("tv", media_id, source)
                seasons = (base.get("related") or {}).get("seasons") or []
                season_numbers = [
                    season["season_number"]
                    for season in seasons
                    if season.get("season_number") is not None
                ]
            if not season_numbers:
                return {}
            grouped = services.get_media_metadata(
                "tv_with_seasons",
                media_id,
                source,
                season_numbers,
            )
    except services.ProviderAPIError:
        logger.warning(
            "Progress breakdown could not load episodes for media_id=%s",
            media_id,
            exc_info=True,
        )
        return {}
    payloads = {}
    for number in season_numbers:
        payload = grouped.get(f"season/{number}")
        if isinstance(payload, dict):
            payloads[number] = payload
    return payloads


def _episode_rows(payload, watched_numbers, pass_numbers, link, now):
    """Merge a catalogue season with the watched numbers into episode rows."""
    rows = {}
    for episode in (payload or {}).get("episodes") or []:
        number = episode.get("episode_number")
        if number is None:
            continue
        air_date = coerce_episode_datetime(episode.get("air_date"))
        if number in watched_numbers:
            state = WATCHED
        elif air_date is not None and air_date <= now:
            state = UNWATCHED
        else:
            state = UPCOMING
        rows[number] = {
            "number": number,
            "title": episode.get("name") or episode.get("title") or "",
            "air_date": air_date,
            "runtime": _runtime_minutes(
                episode.get("runtime_minutes") or episode.get("runtime"),
            ),
            "state": state,
            "rewatched": number in pass_numbers,
        }
    # A play of an episode the catalogue no longer lists still counts for the
    # card, so it has to count here or the two would disagree.
    for number in watched_numbers - rows.keys():
        rows[number] = {
            "number": number,
            "title": "",
            "air_date": None,
            "runtime": 0,
            "state": WATCHED,
            "rewatched": number in pass_numbers,
        }
    ordered = [rows[number] for number in sorted(rows)]
    for row in ordered:
        row["url"] = link(row["number"])
    return ordered


def build_progress_breakdown(*, tv=None, season=None):
    """Return the breakdown for a tracked show, or for one tracked season."""
    if (tv is None) == (season is None):
        msg = "Pass exactly one of tv or season."
        raise ValueError(msg)

    if season is not None:
        tv = season.related_tv
        tracked = [season]
        media_id, source = season.item.media_id, season.item.source
        requested = [season.item.season_number]
    else:
        tracked = list(
            Season.objects.filter(related_tv=tv)
            .select_related("item")
            .prefetch_related("episodes__item"),
        )
        media_id, source = tv.tracking_media_id, tv.tracking_source
        requested = None

    title = tv.item.title
    payloads = _season_payloads(media_id, source, requested)
    by_number = {tracked_season.item.season_number: tracked_season for tracked_season in tracked}
    now = timezone.now()

    def link_for(season_number):
        def link(episode_number):
            return media_url(
                {
                    "media_type": "episode",
                    "source": source,
                    "media_id": media_id,
                    "title": title,
                    "season_number": season_number,
                    "episode_number": episode_number,
                },
            )

        return link

    seasons = []
    for number in sorted(payloads.keys() | by_number.keys()):
        tracked_season = by_number.get(number)
        payload = payloads.get(number)
        watched_numbers = (
            tracked_season.watched_once_numbers if tracked_season else set()
        )
        pass_numbers = (
            tracked_season.completed_episode_numbers if tracked_season else set()
        )
        default_title = "Specials" if number == 0 else f"Season {number}"
        seasons.append(
            SeasonProgress(
                number=number,
                title=(payload or {}).get("season_title") or default_title,
                url=media_url(
                    {
                        "media_type": "season",
                        "source": source,
                        "media_id": media_id,
                        "title": title,
                        "season_number": number,
                    },
                ),
                dropped=bool(
                    tracked_season and tracked_season.status == Status.DROPPED.value,
                ),
                rewatching=bool(tracked_season and tracked_season.is_rewatching),
                catalogue_missing=payload is None,
                episodes=_episode_rows(
                    payload,
                    watched_numbers,
                    pass_numbers,
                    link_for(number),
                    now,
                ),
            ),
        )

    return ProgressBreakdown(
        title=title,
        seasons=seasons,
        catalogue_unavailable=not payloads,
        single_season=season is not None,
    )
