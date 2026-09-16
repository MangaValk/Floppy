# MAL Sync handoff — Floppy MyAnimeList watch-status sync

Written 2026-09-16 for the agent taking over in VS Code. This wasn't developed as a
pushed branch or PR — it exists as a patch file, built and verified by Claude in a
sandboxed environment with no Docker and no push access to the repo. Read this before
doing anything else; it'll save you from re-deriving things the hard way.

## Where the work actually is

| What | Where |
| --- | --- |
| The patch | `floppy-mal-sync.patch` — ask the user for it if it's not already in your workspace |
| Base commit | `c89545cd` on upstream `latest` (last re-verified applying cleanly against a clone at `e31fa120`; this repo moves fast, expect drift — see "If the patch doesn't apply") |
| Setup/testing doc | `testing-mal-sync-on-unraid.md` — also given to the user |

No branch or PR exists yet. Start by applying the patch to a fresh checkout of `latest`:
`git apply floppy-mal-sync.patch` from the repo root.

## What this adds

One-way sync: Floppy → MyAnimeList. Pushes status/progress/score changes for
MAL-tracked anime/manga to the user's MyAnimeList account automatically on save, plus a
manual "Sync All Now" bulk push. Never pulls from MAL back into Floppy — that's the
separate, pre-existing MAL import feature.

| File | Change |
| --- | --- |
| `src/integrations/mal_sync.py` | **new.** OAuth2+PKCE (plain method only — MAL doesn't support S256) exchange/refresh, status/score/progress mapping, the PATCH push call |
| `src/integrations/models.py` | **new** `MALAccount` model, styled like `LastFMAccount` (`connection_broken` / `last_error_message` / `last_failed_at`), not a bespoke shape |
| `src/integrations/migrations/0037_malaccount.py`, `0048_merge_...py` | model migration + a merge migration (upstream had grown its own migration chain from the same branch point) |
| `src/integrations/tasks/_mal_sync.py` | **new.** `sync_mal_status` (per-item, fires on save) + `bulk_sync_mal_status` ("Sync All Now") |
| `src/integrations/tasks/__init__.py` | registers the two new tasks |
| `src/app/models/media.py` | `Anime.save()` / `Manga.save()` hooks, added *alongside* Floppy's existing completed-anime auto-migration-to-episode-tracking logic, not replacing it |
| `src/integrations/views.py`, `src/integrations/urls.py` | connect / callback / disconnect / toggle / full-sync views, reusing the existing `_consume_oauth_state`, `_integration_redirect`, `supports_oauth_redirect` helpers |
| `src/app/providers/credentials.py` | added a `client_secret` field to MAL's *existing* credential spec (search already had `client_id`), so sync correctly inherits Floppy's per-user credential override system |
| `src/app/providers/services.py` | added PATCH method support to `api_request` (MAL's write endpoint needs it) |
| `src/config/settings.py` | `MAL_API_SECRET` env var, mirrors `MAL_API`'s existing pattern |
| `src/templates/users/import_data.html` | sync UI added *inside the existing MyAnimeList modal*, not a new one, plus a connected-badge on the summary card |
| `src/users/views.py` | `mal_account` context wiring; also added `mal_account` to `_get_import_data_user`'s batched `select_related` (upstream added that helper after this work started — worth confirming it's still current) |
| `src/integrations/tests/test_mal_sync.py` | **new**, 38 tests |

## Design decisions that still bind

- **HTTPS required, no fallback.** `supports_oauth_redirect()` rejects any non-loopback
  plain-HTTP redirect URI, and unlike Trakt, MAL has no device-code alternative. Don't
  add one without checking MAL's actual API docs — they don't support it.
- **Per-user credentials, not just instance-wide.** Sync uses
  `credentials.get("mal", "client_id"/"client_secret", user=...)`, so each user can
  bring their own MyAnimeList API app, or the instance can set `MAL_API` /
  `MAL_API_SECRET` as a shared default. Don't read `settings.MAL_API` directly here.
- **PKCE "plain" method only.** MAL doesn't support S256 — code_challenge ==
  code_verifier. That's a MAL limitation, not a shortcut taken in this code.
- **`Anime.all_objects`, not `Anime.objects`, inside the sync tasks.** The default
  `ActiveAnimeManager` hides anime Floppy has auto-migrated to episode tracking on
  completion. Both tasks deliberately use `all_objects` so a just-completed anime still
  gets its final push.
- **Known gap:** edits made *after* that auto-migration (to the resulting TV/Season
  entry, not the original flat Anime row) aren't covered — nothing hooks that save
  path yet. Status/progress/score changes up through completion sync correctly. If
  closing this gap, start from `_auto_migrate_completed_flat_anime` in
  `app/models/media.py`.
- MAL only accepts whole-number scores (0–10); Floppy's one-decimal score gets
  `round()`-ed before sending.

## Verified, and how

Actually run, not assumed — against a venv built from Floppy's real pinned
dependencies (`pyproject.toml`'s `dependencies` + `test` group; `floppy-mcp` excluded
since it's a `uv` workspace package not needed to test this):

- `manage.py check` and `makemigrations --check --dry-run`: clean
- `ruff check` / `ruff format --check` on every changed file: clean
- All 38 new tests pass
- Targeted regression run against the highest-risk existing tests (anime
  completion/migration tests, media model tests, the modified `import_data` template
  render test, OAuth view tests) — passing, not just the new ones
- The patch applies cleanly to a **freshly cloned** copy of the repo, checked
  repeatedly as upstream moved during this work, not just the working copy it was
  built in
- Diffed the full change-set against `origin/latest` line-by-line specifically to
  catch accidental noise from `ruff format` touching unrelated code during cleanup —
  found and fixed several instances of this

**Not verified — no Docker in the sandbox this was built in:**

- Whether `docker build .` actually succeeds with these changes. The Python/Django
  layer is solid; the container build itself is unconfirmed. **Do this first.**
- The Dockerfile's npm/frontend build stage wasn't touched by this patch, but wasn't
  exercised either.

## If the patch doesn't apply

This repo moves fast — 98 commits landed mid-work at one point during this. If
`git apply` fails:

1. Check `git log -1` against the base commit above; if it's moved, that's why.
2. Don't force a rebase through blindly. When this happened mid-build, a straight
   rebase produced real conflicts *and* silently reintroduced stale pre-refactor code
   in two unrelated spots (a Trakt OAuth line, the Stremio addon manifest) that only
   got caught by diffing the final result against `origin/latest` line-by-line rather
   than trusting the rebase's "clean" auto-merges. Do the same check after resolving
   any conflicts: `git diff origin/latest HEAD -- <files>` and actually read every `-`
   line before trusting it.
3. Migration numbering will likely collide again under `integrations/migrations/`.
   Resolve with `manage.py makemigrations --merge`, don't hand-edit `dependencies`.

## Also worth knowing (not part of this patch)

- **Unrelated security issue, still open as far as I know:**
  `yamtrackdb_20260729_011502.sql.gz`, committed to this public repo, is a real
  production database dump — contains a real user's password hash and what looks like
  a live TOTP secret. Flagged to the user earlier; status of a fix is unknown. Worth
  checking before anything else if you have repo access.
- Upstream has been building a generic `OutboundStateDelivery` / `deliver_watched_state`
  mechanism (new since this patch was started — see migrations `0038`–`0039`).
  Conceptually adjacent to what this patch hand-rolls for MAL. Not adopted here for
  time reasons; worth a look before building the *next* outbound sync integration,
  though this one works fine as-is.
