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
        sys.stderr.write('[start02-provider-mock] '+json.dumps(
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


# Lightweight root-interpreter accounting; profile only separate diagnostic runs.
if os.geteuid() == 0 and Path('/results').is_dir():
    import atexit
    started_python = time.monotonic()
    argv = sys.orig_argv
    label = 'python'
    if 'collectstatic' in argv:
        label = 'collectstatic'
    elif any(arg.endswith('static_collection.py') for arg in argv):
        label = 'static_check'
    elif 'migrate' in argv:
        label = 'migrate'
    elif any('import emit_env' in arg for arg in argv):
        label = 'resource_env'
    elif any('import sizing_report' in arg for arg in argv):
        label = 'sizing_report'
    profile = cProfile.Profile() if os.environ.get('START02_PROFILE') == '1' else None
    if profile:
        profile.enable()

    def finished_python():
        if profile:
            profile.disable()
            profile.dump_stats('/results/'+label+'.prof')
        usage = resource.getrusage(resource.RUSAGE_SELF)
        with open('/results/python-processes.jsonl', 'a') as out:
            out.write(json.dumps(dict(label=label, argv=argv,
                body_wall_s=time.monotonic()-started_python,
                lifetime_cpu_s=usage.ru_utime+usage.ru_stime,
                maxrss_kib=usage.ru_maxrss,
                io=Path('/proc/self/io').read_text()))+'\n')
    atexit.register(finished_python)
