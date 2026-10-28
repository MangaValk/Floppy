"""Helpers shared by the video plays API and the YouTube importers."""

from urllib.parse import urlparse

from app.image_cache import is_approved_url

MAX_THUMBNAIL_URL_LENGTH = 2048


def approved_thumbnail_url(raw, media_id):
    """Return a thumbnail URL Floppy may store, or empty.

    Only https URLs on the artwork allowlist that point at this video are kept.
    Anything else is dropped, so nothing fetches a caller-supplied URL and one
    video cannot be given another video's poster.

    @param raw - Candidate URL from the caller.
    @param media_id - YouTube video id.
    @returns Approved URL, or "".
    """
    url = str(raw or "").strip()
    if not url or len(url) > MAX_THUMBNAIL_URL_LENGTH:
        return ""
    # An http:// poster would be blocked as mixed content on an https install.
    if not url.lower().startswith("https://") or not is_approved_url(url):
        return ""
    # YouTube thumbnails live at /vi/<videoId>/<name>.jpg.
    parts = urlparse(url).path.strip("/").split("/")
    if len(parts) < 2 or parts[0] not in ("vi", "vi_webp") or parts[1] != media_id:  # noqa: PLR2004
        return ""
    return url
