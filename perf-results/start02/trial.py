"""Disposable, network-isolated full container startup measurement."""
import json
import hashlib
import os
import platform
import resource
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

DB = '/floppy/db/db.sqlite3'


def snapshot():
    root = Path('/sys/fs/cgroup')
    return {name: (root / name).read_text() for name in
            ('cpu.stat', 'io.stat', 'memory.current', 'memory.peak', 'memory.stat')}


if sys.argv[1] == 'queue':
    sys.argv = ['manage.py', 'shell']
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    import django
    django.setup()
    from config.celery import app
    tick = time.monotonic()
    job = app.send_task('celery.accumulate', args=['start02-queue-fixture'], queue='interactive')
    assert list(job.get(timeout=30, interval=0.05)) == ['start02-queue-fixture']
    print(json.dumps(dict(queue='interactive', roundtrip_s=time.monotonic()-tick)))
    sys.exit()

if sys.argv[1] == 'seed':
    sys.argv[0] = 'manage.py'
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    import django
    django.setup()
    from django.core.management import call_command
    from app.models import Item, Movie
    from users.models import User
    call_command('migrate', interactive=False, verbosity=0)
    user = User.objects.filter(username='start02').first()
    if user is None:
        user = User.objects.create_user(username='start02', password='fixture-only')
    count = int(sys.argv[2])
    for offset in range(Item.objects.count(), count, 1000):
        items = Item.objects.bulk_create([Item(media_id=str(i), source='manual',
            title=f'Fixture {i}', synopsis='x' * 2048)
            for i in range(offset, min(count, offset+1000))])
        Movie.objects.bulk_create([Movie(item=item, user=user) for item in items])
    conn = sqlite3.connect(DB)
    conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    assert conn.execute('PRAGMA quick_check').fetchall() == [('ok',)]
    assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
    metadata = dict(items=Item.objects.count(), movies=Movie.objects.count(),
        users=User.objects.count(), bytes=Path(DB).stat().st_size,
        pages=conn.execute('PRAGMA page_count').fetchone()[0],
        freelist=conn.execute('PRAGMA freelist_count').fetchone()[0],
        sqlite=sqlite3.sqlite_version, python=sys.version, django=django.get_version())
    conn.close()
    Path('/floppy/db/fixture.json').write_text(json.dumps(metadata, indent=2))
    print(json.dumps(metadata))
    sys.exit()

if sys.argv[1] == 'prepare':
    sys.argv[0] = 'manage.py'
    fixture = Path('/floppy/db/fixture.sqlite3')
    if not fixture.exists():
        source = sqlite3.connect(DB)
        destination = sqlite3.connect(fixture)
        source.backup(destination)
        destination.close()
        source.close()
    for suffix in ('-wal', '-shm'):
        Path(DB+suffix).unlink(missing_ok=True)
    shutil.copyfile(fixture, DB+'.restored')
    Path(DB+'.restored').replace(DB)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    import django
    django.setup()
    from django.core.cache import cache
    # Controlled provider fixtures: never time outbound catalog requests.
    cache.set('tmdb_watch_provider_catalog', [], timeout=None)
    cache.set('tmdb_watch_provider_regions', [('', 'Disabled')], timeout=None)
    from django.contrib.sessions.backends.db import SessionStore
    from users.models import User
    user = User.objects.get(username='start02')
    session = SessionStore()
    session['_auth_user_id'] = str(user.pk)
    session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
    session['_auth_user_hash'] = user.get_session_auth_hash()
    session.save()
    Path('/floppy/db/session.txt').write_text(session.session_key)
    from config.sqlite_integrity import record_verified_database, _verified_path
    # Keep the same inode: verification binds device/inode, not a copied sidecar.
    for suffix in ('integrity.status.json', 'integrity.verified.json'):
        Path(f'{DB}.{suffix}').unlink(missing_ok=True)
    if sys.argv[2] == 'verified':
        record_verified_database(DB, source='startup')
    else:
        _verified_path(DB).unlink(missing_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    conn.close()
    for path in (DB, DB+'-wal'):
        if Path(path).exists():
            with open(path, 'rb') as f:
                os.fsync(f.fileno())
                if sys.argv[3] == 'cold':
                    os.posix_fadvise(f.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
                else:
                    while f.read(1024*1024):
                        pass
    sys.exit()

result = dict(fixture=json.loads(Path('/floppy/db/fixture.json').read_text()),
              protocol='sequential-health-then-library-v2',
              platform=platform.platform(), limits=resource.getrlimit(resource.RLIMIT_NOFILE),
              host_loadavg_start=os.getloadavg(),
              database_bytes_at_start=Path(DB).stat().st_size,
              wal_bytes_at_start=Path(DB+'-wal').stat().st_size if Path(DB+'-wal').exists() else 0)
start = time.monotonic()
result['started_epoch'] = time.time()
result['initial'] = snapshot()
log = open('/results/container.log', 'w')
proc = subprocess.Popen(['/runtime-entrypoint.sh'], stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True, start_new_session=True)
stages = []


def logs():
    for line in proc.stdout:
        log.write(line)
        log.flush()
        if '[entrypoint]' in line or '[integrity]' in line or 'ready.' in line:
            stages.append(dict(seconds=time.monotonic()-start, message=line.strip(),
                               counters=snapshot()))


threading.Thread(target=logs, daemon=True).start()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
while time.monotonic()-start < 300:
    probes = [('healthy_s', '/health/')] if 'healthy_s' not in result else [('usable_s', '/medialist/movie')]
    for key, url in probes:
        if key in result:
            continue
        try:
            request = urllib.request.Request('http://127.0.0.1:8000'+url,
                headers={'Cookie': 'sessionid='+Path('/floppy/db/session.txt').read_text()})
            with opener.open(request, timeout=10 if key == 'healthy_s' else 60) as response:
                body = response.read()
                if response.status == 200 and (key != 'usable_s' or b'Fixture' in body):
                    result[key] = time.monotonic()-start
                    result[key+'_counters'] = snapshot()
        except Exception:
            pass
    if 'healthy_s' in result and 'usable_s' in result:
        break
    if proc.poll() is not None:
        break
    time.sleep(0.25)
result['ready_counters'] = snapshot()
result['host_loadavg_ready'] = os.getloadavg()
result['wall_s'] = time.monotonic()-start
# Idle, bounded post-ready probes; no user/provider traffic or background load.
latencies = []
for _ in range(10 if 'usable_s' in result else 0):
    tick = time.monotonic()
    request = urllib.request.Request('http://127.0.0.1:8000/medialist/movie',
        headers={'Cookie': 'sessionid='+Path('/floppy/db/session.txt').read_text()})
    with opener.open(request, timeout=60) as response:
        assert response.status == 200
        response.read()
    latencies.append(time.monotonic()-tick)
result['library_latency_s'] = latencies
webhooks = []
for _ in range(10 if 'usable_s' in result else 0):
    tick = time.monotonic()
    request = urllib.request.Request('http://127.0.0.1:8000/webhook/plex/invalid-fixture-token',
                                     data=b'{}', headers={'Content-Type': 'application/json'})
    try:
        opener.open(request, timeout=5).close()
        code = 200
    except urllib.error.HTTPError as error:
        code = error.code
    webhooks.append(dict(seconds=time.monotonic()-tick, status=code))
result['webhook_rejection'] = webhooks
if os.environ.get('START02_QUEUE_CANARY') == '1':
    canary = subprocess.run([sys.executable, '/bench/trial.py', 'queue'],
                            capture_output=True, text=True)
    assert canary.returncode == 0, canary.stdout + canary.stderr
    result['interactive_queue_canary'] = json.loads(canary.stdout.splitlines()[-1])
conn = sqlite3.connect(DB)
result['correctness'] = dict(
    quick_check=conn.execute('PRAGMA quick_check').fetchall(),
    foreign_key_check=conn.execute('PRAGMA foreign_key_check').fetchall(),
    items=conn.execute('SELECT COUNT(*) FROM app_item').fetchone()[0],
    movies=conn.execute('SELECT COUNT(*) FROM app_movie').fetchone()[0],
    migrations=conn.execute('SELECT COUNT(*) FROM django_migrations').fetchone()[0])
conn.close()
assert result['correctness']['quick_check'] == [('ok',)]
assert result['correctness']['foreign_key_check'] == []
assert result['correctness']['items'] == result['fixture']['items']
assert result['correctness']['movies'] == result['fixture']['movies']
assets = Path('/floppy/staticfiles')
result['static_assets'] = {str(path.relative_to(assets)): dict(
    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    uid=path.stat().st_uid, gid=path.stat().st_gid)
    for path in sorted(assets.rglob('*')) if path.is_file()}
with opener.open('http://127.0.0.1:8000/static/css/main.css', timeout=15) as response:
    assert response.status == 200
    assert hashlib.sha256(response.read()).hexdigest() == result['static_assets']['css/main.css']['sha256']
assert all(asset['uid']==int(os.environ.get('PUID', '1000')) and asset['gid']==int(os.environ.get('PGID', '1000')) for asset in result['static_assets'].values())
result['startup_status'] = json.loads(Path(DB+'.integrity.status.json').read_text())
result['stages'] = stages
result['processes'] = subprocess.run(['ps', '-o', 'pid,ppid,rss,args'], capture_output=True, text=True).stdout
result['sizing'] = json.loads(Path('/tmp/floppy-boot-sizing.json').read_text()) if Path('/tmp/floppy-boot-sizing.json').exists() else None
Path('/results/result.json').write_text(json.dumps(result, indent=2))
print(json.dumps({key: result.get(key) for key in ('healthy_s', 'usable_s', 'wall_s')}), flush=True)
if 'usable_s' not in result:
    sys.exit(1)
