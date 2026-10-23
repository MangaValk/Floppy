"""The Plex modal on Sync to Trackers: choose a Plex user and preview a push.

Both views only read. The Home user token and PIN live for one request; the
preview is rendered straight from the plan and nothing about it is stored.
"""

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from integrations import plex as plex_api
from integrations import plex_watched_push
from integrations.models import PlexAccount
from integrations.safe_fetch import UnsafeUrlError

TARGETS_TEMPLATE = "users/components/plex_push_targets.html"
PREVIEW_TEMPLATE = "users/components/plex_push_preview.html"
# Long enough to cover a dry run that hits the web worker's timeout.
PREVIEW_LOCK_SECONDS = 300


def _account(user):
    account = PlexAccount.objects.filter(user=user).first()
    return account if account and account.plex_token else None


@login_required
@require_GET
def plex_push_targets(request):
    """Render the Plex user and server pickers."""
    account = _account(request.user)
    if account is None:
        return render(request, TARGETS_TEMPLATE, {"error": "Connect Plex first."})
    try:
        users, servers = plex_watched_push.list_targets(account)
    except plex_api.PlexAuthError:
        error = "Plex rejected the saved token. Reconnect Plex."
        return render(request, TARGETS_TEMPLATE, {"error": error})
    except plex_api.PlexClientError:
        error = "Plex could not be reached. Try again."
        return render(request, TARGETS_TEMPLATE, {"error": error})
    return render(request, TARGETS_TEMPLATE, {"users": users, "servers": servers})


@login_required
@require_POST
def plex_push_preview(request):
    """Render what a push would change for the chosen Plex user. Writes nothing."""
    account = _account(request.user)
    if account is None:
        return render(request, PREVIEW_TEMPLATE, {"error": "Connect Plex first."})

    lock = f"plex_push_preview:{request.user.pk}"
    if not cache.add(lock, 1, timeout=PREVIEW_LOCK_SECONDS):
        error = "A check is already running. Wait for it to finish."
        return render(request, PREVIEW_TEMPLATE, {"error": error})
    try:
        session = plex_watched_push.open_session(
            account,
            request.POST.get("user_uuid", ""),
            request.POST.get("machine_identifier", ""),
            request.POST.get("pin") or None,
        )
        plan = plex_watched_push.build_plan(request.user, account, session)
    except plex_watched_push.PlexPushError as error:
        return render(request, PREVIEW_TEMPLATE, {"error": str(error)})
    except plex_api.PlexAuthError:
        error = "Plex refused access. Check the PIN, or reconnect Plex."
        return render(request, PREVIEW_TEMPLATE, {"error": error})
    except (plex_api.PlexClientError, UnsafeUrlError):
        error = "Plex could not be reached. Try again."
        return render(request, PREVIEW_TEMPLATE, {"error": error})
    finally:
        cache.delete(lock)

    return render(
        request,
        PREVIEW_TEMPLATE,
        {"session": session, "plan": plan},
    )
