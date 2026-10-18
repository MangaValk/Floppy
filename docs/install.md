# Guided installation

One command installs Floppy, starts it, and hands you a URL. It asks a few
plain questions and never asks for a password or an API key.

```bash
curl -fsSL https://raw.githubusercontent.com/dannyvfilms/Floppy/latest/scripts/install.sh -o /tmp/floppy-install.sh && bash /tmp/floppy-install.sh
```

The download and the run are separate steps on purpose: the installer is
interactive, and piping it straight into a shell would leave it without a
terminal to ask questions on.

## What it asks

1. **How Floppy should run** - Docker (recommended) or directly on this
   computer.
2. **Who can reach it** - other devices on your network, or only this computer.
3. **Which port**, and **which time zone**. Both come with a detected default.

It then lists anything it needs to install and any step needing administrator
access, and asks before doing it. Nothing is installed without a yes.

Once Floppy answers, the installer prints the address, asks you to create your
account in the browser, and then asks for that username so it can make the
account the owner. It never asks for the password.

## Where it works

| Host | Docker | Directly on this computer |
| --- | --- | --- |
| Ubuntu / Debian | Installs Docker for you, with permission | systemd services |
| Other Linux with Docker | Yes | Use Docker |
| macOS | Needs Docker Desktop running | launchd services, via Homebrew |
| WSL2 | Yes | Use Docker |

An unsupported host is told exactly which prerequisite is missing rather than
being half-installed.

## What it creates

```
~/floppy/                 the installation root (you choose the path)
  repo/                   the checkout (currently the latest branch;
                          see the TODO in scripts/install.sh)
  floppy.env              this installation's settings
  install.conf            the answers needed to resume
  db/                     the database and the generated secret key
  backups/                automatic database backups
  logs/                   log files
  redis/                  Redis persistence
  docker-compose.yml      Docker installs only
  run/                    source installs only: service configuration
```

Runtime data lives beside the checkout, never inside it, so updating the code
cannot touch the database. Back up this root with Floppy stopped, or use a
consistent database snapshot; copying a live SQLite file alone is unsafe.
Keep an encrypted copy on another disk or machine, including the original
signing key and external secret files. PostgreSQL needs a consistent
`pg_dump` backup rather than a copy of its live data volume. Native macOS SQLite
snapshots use a private system-temporary workspace, requiring room for another
full database copy there as well as in `backups/`. Linux snapshots stage directly
in the backup directory. Both verify before atomic publication. Monitor backup
file dates and failure logs; a running scheduler does not prove backups succeed.

## Running it again

Rerunning the installer is safe. It never resets the checkout, overwrites the
configuration, changes the installation method, or adopts an installation it
did not create. It offers to start Floppy again, or to finish owner setup if
you skipped it.

## Afterwards

The installer prints the exact start, stop, status, logs, and resume commands
for the method you chose. In short:

**Docker**

```bash
docker compose -f ~/floppy/docker-compose.yml up -d       # start
docker compose -f ~/floppy/docker-compose.yml down        # stop
docker compose -f ~/floppy/docker-compose.yml logs -f     # logs
```

For upgrades, record the current image digest, stop Floppy, and make a complete
backup first. Pin the desired image in the generated Compose file, then run
`pull` and `up -d` with that file. Startup applies migrations automatically.
Do not use `down -v`. Rollback requires restoring the pre-upgrade database,
matching key/configuration, and old image together; an older image alone
cannot safely undo database migrations.

**Source, Linux — start and stop**

```bash
sudo systemctl start floppy
sudo systemctl stop floppy
```

**Source, macOS — start and stop**

```bash
sudo launchctl bootstrap system /Library/LaunchDaemons/com.floppy.app.plist
sudo launchctl bootout system /Library/LaunchDaemons/com.floppy.app.plist
```

Normal `migrate` on an existing database also stops at the `v26.10.1` graph
conflict, before applying migrations. Move to a release/source revision that
contains `users/0141_merge_search_all_discover_seerr.py`, keeping the database
and original key intact. That migration joins the three published leaves; do
not generate a local merge, edit published migrations, or fake their records.
A database already modified by manual repairs needs individual assessment.

**Source upgrades (both systems)**

Stop the service using the command above and back up the installation root
before changing code. Record the old commit. Then, as the installation owner,
run this for the default root (adjust paths if yours differs):

```bash
(
  set -e
  cd ~/floppy/repo
  git pull --ff-only
  ~/floppy/bin/uv sync --locked --no-default-groups
  set -a
  . ~/floppy/floppy.env
  set +a
  .venv/bin/python src/manage.py migrate --noinput
  .venv/bin/python src/manage.py collectstatic --noinput
  .venv/bin/python src/manage.py check
)
```

The installer may use an existing compatible `uv` instead of installing
`~/floppy/bin/uv`; use that executable if the latter is absent. Run the start
command only after every step succeeds. A normal source service start does
not apply migrations or collect static files. A failed migration can leave
earlier migrations applied; restoring the pre-upgrade database and old code
is the reliable fallback, with loss of writes since that backup.

Metadata API keys are entered in Floppy itself, under **Settings → Metadata**.
Floppy works without them.

## What this does not do

Automatic upgrades, moving an installation between Docker and source,
PostgreSQL setup, and public HTTPS are all deliberately out of scope. The
existing Compose and Unraid instructions in [README.md](../README.md) are
unchanged and remain the right path for those.

## If it does not finish

The installer waits five minutes for Floppy to answer. On a timeout it leaves
the services running and your data alone, says startup may still be in
progress, and prints bounded diagnostics. Run it again to resume, or run the
built-in check:

```bash
docker compose -f ~/floppy/docker-compose.yml exec floppy python manage.py floppy_preflight
```
