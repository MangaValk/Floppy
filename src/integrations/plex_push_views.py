"""The Send Watched to Plex modal: choose a Plex user, preview, then send.

The Home user token and PIN live for one request; the preview is rendered
straight from the plan and nothing about it is stored. Only the send writes.
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
RESULT_TEMPLATE = "users/components/plex_push_result.html"
# Long enough to cover a request that hits the web worker's timeout.
PUSH_LOCK_SECONDS = 300


def _account(user):
    account = PlexAccount.objects.filter(user=user).first()
    return account if account and account.plex_token else None


def _with_session(request, template, action):
    """Open a Plex session for the posted user and render ``action``'s context.

    One preview or send runs at a time per user, so a double click cannot
    send twice.
    """
    account = _account(request.user)
    if account is None:
        return render(request, template, {"error": "Connect Plex first."})

    lock = f"plex_push:{request.user.pk}"
    if not cache.add(lock, 1, timeout=PUSH_LOCK_SECONDS):
        error = "A check or send is already running. Wait for it to finish."
        return render(request, template, {"error": error})
    try:
        session = plex_watched_push.open_session(
            account,
            request.POST.get("user_uuid", ""),
            request.POST.get("machine_identifier", ""),
            request.POST.get("pin") or None,
        )
        context = action(account, session)
    except plex_watched_push.PlexPushError as error:
        return render(request, template, {"error": str(error)})
    except plex_api.PlexAuthError:
        error = "Plex refused access. Check the PIN, or reconnect Plex."
        return render(request, template, {"error": error})
    except (plex_api.PlexClientError, UnsafeUrlError):
        error = "Plex could not be reached. Try again."
        return render(request, template, {"error": error})
    finally:
        cache.delete(lock)
    return render(request, template, {"session": session, **context})


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
    return _with_session(
        request,
        PREVIEW_TEMPLATE,
        lambda account, session: {
            "plan": plex_watched_push.build_plan(request.user, account, session),
            "max_writes": plex_watched_push.MAX_WRITES_PER_SEND,
        },
    )


@login_required
@require_POST
def plex_push_send(request):
    """Mark the ticked preview rows watched in Plex for the chosen user."""
    selected = set()
    for value in request.POST.getlist("write"):
        rating_key, _, item_id = value.rpartition(":")
        if rating_key and item_id.isdigit():
            selected.add((rating_key, int(item_id)))
    if not selected:
        return render(request, RESULT_TEMPLATE, {"error": "Tick at least one item."})
    if len(selected) > plex_watched_push.MAX_WRITES_PER_SEND:
        error = (
            f"Tick at most {plex_watched_push.MAX_WRITES_PER_SEND} items per send. "
            "Send the rest afterwards."
        )
        return render(request, RESULT_TEMPLATE, {"error": error})

    return _with_session(
        request,
        RESULT_TEMPLATE,
        lambda account, session: {
            "result": plex_watched_push.send(request.user, account, session, selected),
        },
    )
