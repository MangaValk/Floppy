"""Benchmark-only instrumentation; loaded through PYTHONPATH, never shipped."""
import cProfile
import json
import os
import resource
import sys
import time
from pathlib import Path

# A cold/failing Redis cache must not turn the library probe into provider I/O.
# Keep this off the integrity/migration interpreters being profiled.
if any(arg.endswith(('/gunicorn', '/celery')) for arg in sys.orig_argv):
    import requests
    from urllib.parse import urlsplit

    original_request = requests.sessions.Session.request

    def fixture_request(self, method, url, *args, **kwargs):
        parsed = urlsplit(url)
        if parsed.hostname in {'127.0.0.1', 'localhost'}:
            return original_request(self, method, url, *args, **kwargs)
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response._content = b'{"results": []}'
        sys.stderr.write('[start01-provider-mock] '+json.dumps(
            dict(host=parsed.hostname, path=parsed.path))+'\n')
        return response

    requests.sessions.Session.request = fixture_request

if any("check_database_for_startup" in arg for arg in sys.orig_argv):
    from config import sqlite_recovery_policy as policy

    def instrument(name):
        original = getattr(policy, name)

        def measured(*args, **kwargs):
            started = time.monotonic()
            cpu = time.process_time()
            before = Path('/proc/self/io').read_text()
            profiler = cProfile.Profile()
            try:
                profiler.enable()
                if name == '_warm_cache' and os.environ.get('START01_NO_WARM') == '1':
                    return None
                return original(*args, **kwargs)
            finally:
                profiler.disable()
                profiler.dump_stats(f'/results/{name}.prof')
                with open('/results/stages.jsonl', 'a') as out:
                    out.write(json.dumps(dict(stage=name, wall_s=time.monotonic()-started,
                        cpu_s=time.process_time()-cpu, io_before=before,
                        io_after=Path('/proc/self/io').read_text(),
                        maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))+'\n')

        setattr(policy, name, measured)

    for name in ('_skip_recently_verified', '_warm_cache', '_scan_and_publish_block'):
        instrument(name)
