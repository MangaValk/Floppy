"""Host orchestrator. Requires Docker; uses only disposable named resources."""
import argparse
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--variant', choices=['baseline', 'no-warm'], default='baseline')
parser.add_argument('--smoke', action='store_true')
parser.add_argument('--cold-only', action='store_true', help='Collect required cold repeats on a contended host')
args = parser.parse_args()
ROOT = Path(__file__).resolve().parent
IMAGE = 'floppy:start01-baseline'
NETWORK = 'floppy-start01-isolated'
SHA = '27b89e56a5a91548ebd4a84eba2fc5bce119fff4'


def docker(*cmd, check=True):
    result = subprocess.run(['docker', *cmd], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and result.returncode:
        raise RuntimeError(result.stdout[-4000:])
    return result.stdout


env = ['-e', 'SECRET=start01-disposable-only', '-e', 'REDIS_URL=redis://floppy-start01-redis:6379',
       '-e', 'WEB_CONCURRENCY=1', '-e', 'GUNICORN_THREADS=2', '-e', 'CELERY_WORKER_CONCURRENCY=1',
       '-e', 'FLOPPY_RESOURCE_TIER=standard', '-e', 'PYTHONPATH=/bench:/floppy',
       '-e', 'COMMIT_SHA='+SHA, '-e', 'FLOPPY_NOFILE_LIMIT=4096']
common = ['--network', NETWORK, '--cpus', '2', '--memory', '2g', '--memory-swap', '2g',
          '--pids-limit', '256', '--ulimit', 'nofile=4096:4096', *env,
          '-v', str(ROOT)+':/bench:ro']
docker('network', 'create', '--internal', NETWORK, check=False)
docker('run', '-d', '--name', 'floppy-start01-redis', '--network', NETWORK,
       'redis:8-alpine', 'redis-server', '--save', '', '--appendonly', 'no', check=False)
try:
    for size, count in [('small', 1000), ('large', 100000)]:
        volume = 'floppy-start01-'+size
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
                    '-v', 'floppy-start01-small:/seed:ro', '--entrypoint', 'python', IMAGE,
                    '-c', 'import sqlite3; source=sqlite3.connect("file:/seed/db.sqlite3?mode=ro",uri=True); dest=sqlite3.connect("/floppy/db/db.sqlite3"); source.backup(dest); dest.close(); source.close()')
            print(docker('run', '--rm', *common, *mounts, '--entrypoint', 'python', IMAGE,
                         '/bench/trial.py', 'seed', str(count))[-1500:], flush=True)
        for verification in ['unverified', 'verified']:
            for cache, trials in [('cold', 3), ('warm', 6)]:
                if args.cold_only and cache != 'cold':
                    continue
                for run in range(1 if args.smoke else trials):
                    name = f'{args.variant}-{size}-{verification}-{cache}-{run}'
                    output = ROOT/'raw'/name
                    output.mkdir(parents=True, exist_ok=True)
                    if (output/'result.json').exists():
                        continue
                    docker('exec', 'floppy-start01-redis', 'redis-cli', 'FLUSHALL')
                    docker('run', '--rm', *common, *mounts, '--entrypoint', 'python', IMAGE,
                           '/bench/trial.py', 'prepare', verification, cache)
                    container = 'floppy-start01-trial'
                    docker('rm', '-f', container, check=False)
                    try:
                        print(name, flush=True)
                        print(docker('run', '--name', container, *common, *mounts,
                            '-v', str(output)+':/results', '-e', 'START01_NO_WARM='+str(int(args.variant == 'no-warm')),
                            '--entrypoint', 'python', IMAGE, '/bench/trial.py', 'run')[-1200:], flush=True)
                        (output/'inspect.json').write_text(docker('inspect', container))
                    finally:
                        docker('rm', '-f', container, check=False)
finally:
    docker('rm', '-f', 'floppy-start01-redis', check=False)
    docker('network', 'rm', NETWORK, check=False)
