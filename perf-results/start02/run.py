"""Host orchestrator. Requires Docker; uses only disposable named resources."""
import argparse
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--variant', choices=['baseline', 'changed'], default='baseline')
parser.add_argument('--smoke', action='store_true')
parser.add_argument('--sizes', nargs='+', choices=['small', 'large'], default=['small', 'large'])
parser.add_argument('--verification', choices=['both', 'verified', 'unverified'], default='both')
parser.add_argument('--warm-only', action='store_true')
parser.add_argument('--index', type=int)
parser.add_argument('--queue-canary', action='store_true')
parser.add_argument('--label')
parser.add_argument('--puid', default='1000')
parser.add_argument('--pgid', default='1000')
parser.add_argument('--cold-only', action='store_true', help='Collect required cold repeats on a contended host')
args = parser.parse_args()
ROOT = Path(__file__).resolve().parent
IMAGE = 'floppy:start02-'+args.variant
NETWORK = 'floppy-start02-isolated'


def docker(*cmd, check=True):
    result = subprocess.run(['docker', *cmd], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and result.returncode:
        raise RuntimeError(result.stdout[-4000:])
    return result.stdout


image_info = json.loads(docker('image', 'inspect', IMAGE))[0]
SHA = dict(value.split('=', 1) for value in image_info['Config']['Env'])['COMMIT_SHA']
(ROOT/('image-'+args.variant+'.json')).write_text(json.dumps([image_info], indent=2)+'\n')
env = ['-e', 'SECRET=start02-disposable-only', '-e', 'REDIS_URL=redis://floppy-start02-redis:6379',
       '-e', 'PUID='+args.puid, '-e', 'PGID='+args.pgid, '-e', 'WEB_CONCURRENCY=1', '-e', 'GUNICORN_THREADS=2', '-e', 'CELERY_WORKER_CONCURRENCY=1',
       '-e', 'FLOPPY_RESOURCE_TIER=standard', '-e', 'PYTHONPATH=/bench:/floppy',
       '-e', 'COMMIT_SHA='+SHA, '-e', 'START02_QUEUE_CANARY='+str(int(args.queue_canary)), '-e', 'FLOPPY_NOFILE_LIMIT=4096']
common = ['--network', NETWORK, '--cpus', '2', '--memory', '2g', '--memory-swap', '2g',
          '--pids-limit', '256', '--ulimit', 'nofile=4096:4096', *env,
          '-v', str(ROOT)+':/bench:ro']
docker('network', 'create', '--internal', NETWORK, check=False)
docker('run', '-d', '--name', 'floppy-start02-redis', '--network', NETWORK,
       'redis:8-alpine', 'redis-server', '--save', '', '--appendonly', 'no', check=False)
try:
    for size, count in [('small', 1000), ('large', 100000)]:
        if size not in args.sizes:
            continue
        volume = 'floppy-start02-'+size
        # Fixture volumes intentionally survive repeat runs until explicit cleanup.
        exists = subprocess.run(['docker', 'volume', 'inspect', volume], capture_output=True).returncode == 0
        docker('volume', 'create', volume)
        mounts = ['-v', volume+':/floppy/db']
        prepared = exists and subprocess.run(['docker', 'run', '--rm', '--network', 'none',
            *mounts, '--entrypoint', 'test', IMAGE, '-f', '/floppy/db/fixture.json'], capture_output=True).returncode == 0
        if not prepared:
            print('seeding', size, flush=True)
            if size == 'large':
                docker('run', '--rm', '--network', 'none', *mounts,
                    '-v', 'floppy-start02-small:/seed:ro', '--entrypoint', 'python', IMAGE,
                    '-c', 'import sqlite3; source=sqlite3.connect("file:/seed/db.sqlite3?mode=ro",uri=True); dest=sqlite3.connect("/floppy/db/db.sqlite3"); source.backup(dest); dest.close(); source.close()')
            print(docker('run', '--rm', *common, *mounts, '--entrypoint', 'python', IMAGE,
                         '/bench/trial.py', 'seed', str(count))[-1500:], flush=True)
        for verification in ['unverified', 'verified']:
            if args.verification != 'both' and verification != args.verification:
                continue
            for cache, trials in [('cold', 3), ('warm', 6)]:
                if args.warm_only and cache != 'warm':
                    continue
                if args.cold_only and cache != 'cold':
                    continue
                for run in range(1 if args.smoke else trials):
                    if args.index is not None and run != args.index:
                        continue
                    name = f'{args.label or args.variant}-{size}-{verification}-{cache}-{run}'
                    output = ROOT/'raw'/name
                    output.mkdir(parents=True, exist_ok=True)
                    if (output/'result.json').exists():
                        continue
                    docker('exec', 'floppy-start02-redis', 'redis-cli', 'FLUSHALL')
                    docker('run', '--rm', *common, *mounts, '--entrypoint', 'python', IMAGE,
                           '/bench/trial.py', 'prepare', verification, cache)
                    container = 'floppy-start02-trial'
                    docker('rm', '-f', container, check=False)
                    try:
                        print(name, flush=True)
                        print(docker('run', '--name', container, *common, *mounts,
                            '-v', str(output)+':/results',
                            '--entrypoint', 'python', IMAGE, '/bench/trial.py', 'run')[-1200:], flush=True)
                        (output/'inspect.json').write_text(docker('inspect', container))
                        (output/'filesystem-diff.txt').write_text(docker('diff', container))
                    finally:
                        docker('rm', '-f', container, check=False)
finally:
    docker('rm', '-f', 'floppy-start02-redis', check=False)
    docker('network', 'rm', NETWORK, check=False)
