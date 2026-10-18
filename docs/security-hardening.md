# Security hardening and upgrade notes

## Celery JSON transition

Celery task and result serializers and accepted content are JSON only. Workers
reject old pickle messages rather than executing them. Uploads already use
shared staging paths; the calendar API now sends a user ID rather than a User
instance. Custom task publishers must send JSON-compatible values (Kombu also
supports typed dates and bytes), not Django models, querysets or open files.

Before upgrading an existing installation:

1. Stop new submissions and all beat/scheduled producers. Keep the old workers
   running on the trusted broker until outstanding work finishes. Check active,
   reserved and scheduled tasks and **both** interactive and background queues,
   including priority queues and Redis unacknowledged deliveries.
2. Stop all old workers and publishers together, then deploy the new version.
   Do not use a mixed-version rolling deployment for this transition.
3. If draining is impossible, explicitly cancel/requeue unfinished imports and
   jobs through their normal workflows. Old pickle messages will be rejected
   and discarded by new workers; they will not be converted automatically, and
   old task rows may continue to show pending. Do not flush a shared Redis or
   delete application data to perform this upgrade.

The prior default result serializer was already JSON. Historical non-JSON
results from custom deployments are no longer readable. Retain a backup and
re-run the supported job if its result is still needed. On rollback, stop new
publishers/workers first; old workers accept JSON, but do not resume accepting
pickle on an untrusted broker.

JSON removes executable broker-message deserialization, not the need to protect
Redis: anyone able to publish can invoke registered tasks with forged arguments.
The Django Redis cache also retains its Python object serializer. Keep Redis on
a trusted network; use authenticated/TLS Redis URLs for a remote service.

## HTTPS and deployment settings

LAN HTTP remains supported. For an HTTPS-only deployment, pass these environment
values to Floppy (a Compose `.env` alone does not pass arbitrary values through):

```text
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
ALLOWED_HOSTS=floppy.example.com
URLS=https://floppy.example.com
REGISTRATION=False
USE_X_FORWARDED_HOST=False
USE_X_FORWARDED_PORT=False
```

Enable `USE_X_FORWARDED_PROTO=True` only behind a trusted proxy that replaces
client-supplied `X-Forwarded-Proto`, and prevent direct client access to the app
listener. Host/port forwarding is separately configurable; leave it off unless
required and sanitized. `URLS` adds trusted origins and hosts; it does not enable
TLS or remove Docker's wildcard default. Set `ALLOWED_HOSTS` explicitly.

Terminate TLS and enforce HTTP-to-HTTPS redirects at the proxy. Enable HSTS there
only after testing HTTPS and deciding which subdomains it covers. Secure cookies
alone do not redirect HTTP. Preserve `SECRET` across upgrades; changing it can
invalidate sessions and make encrypted integration credentials unreadable.

Registration remains on for first-run provisioning; disable it afterward for a
private instance. Keep demo and auto-login off. The shipped Compose stacks publish
only the application port, not Redis/PostgreSQL, and use a stack bridge network.
Do not attach untrusted containers or publish datastore ports. Host networking,
shared namespaces, external Redis, and additional proxy networks need operator
review. No network topology or existing database password is changed here.

## Account recovery

Enabling, replacing or disabling an authenticator and regenerating recovery codes
require the current local password. Password checks use allauth's per-user
`reauthenticate` rate limit. TOTP remains a password-recovery mechanism, not login
MFA. Users with an unusable local password must establish one through their
supported account flow before using these controls; this does not add an SSO
reauthentication protocol. Initial pending QR setup remains visible to the
signed-in user, and pending setup is not a substitute for reauthentication.

## Startup recovery downloads

The startup listener runs before Django on the application port. Its incident
page and diagnostic details remain anonymous so recovery works without Django,
Redis or working authentication. Restrict this listener at the proxy/firewall
when the app is reachable beyond trusted operators. Proxy access rules must
cover the entire application listener, including `/backup`, `/retry`, `/accept`
and `/quarantine`, rather than only normal Django routes.

Database download still defaults off. To enable it temporarily, set both:

- `FLOPPY_SQLITE_ALLOW_BACKUP_DOWNLOAD=true`
- `FLOPPY_SQLITE_BACKUP_TOKEN` to a separately generated random value of at least
  32 characters (for example, `python -c 'import secrets; print(secrets.token_urlsafe(32))'`).

The page now requires this token in a POST form. GET downloads, missing/short
server tokens, wrong tokens and cross-origin browser requests are refused. The
server never embeds the token in the page or URL. Use HTTPS or a trusted local
connection, remove both settings after recovery, and protect downloaded files
like the live database. Existing scripts using GET `/backup` must switch to
POST with a `token` form field. The incident approval code for repairs remains
separate. Prefer copying a verified snapshot directly from the protected volume.
