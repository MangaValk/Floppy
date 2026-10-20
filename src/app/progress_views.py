"""The watched-episodes breakdown opened from a show or season progress card."""

from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from app.models import TV, Season
from app.services.progress_breakdown import build_progress_breakdown


@never_cache
@require_GET
def tv_progress_breakdown(request, tv_id):
    """Return the season and episode breakdown for a tracked show."""
    tv = get_object_or_404(TV.objects.select_related("item"), pk=tv_id, user=request.user)
    return render(
        request,
        "app/components/progress_breakdown.html",
        {"breakdown": build_progress_breakdown(tv=tv)},
    )


@never_cache
@require_GET
def season_progress_breakdown(request, season_id):
    """Return the episode breakdown for a tracked season."""
    season = get_object_or_404(
        Season.objects.select_related("item", "related_tv__item"),
        pk=season_id,
        user=request.user,
    )
    return render(
        request,
        "app/components/progress_breakdown.html",
        {"breakdown": build_progress_breakdown(season=season)},
    )
