"""In-container static correctness cases; never used by application code."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

case = sys.argv[1]
root = Path('/floppy/staticfiles')
helper = Path('/floppy/config/static_collection.py')
source = Path('/floppy/static/css/main.css')
if case == 'debug':
    os.environ['DEBUG'] = 'true'
elif case == 'provider':
    os.environ['SOCIAL_PROVIDERS'] = 'allauth.socialaccount.providers.google'
elif case == 'missing-file':
    (root/'css/main.css').unlink()
elif case == 'empty-root':
    shutil.rmtree(root)
    root.mkdir()
elif case == 'changed-source':
    source.write_bytes(source.read_bytes()+b'\n/* START-02 fixture */\n')
    timestamp = (root/'css/main.css').stat().st_mtime+10
    os.utime(source, (timestamp, timestamp))
elif case == 'bad-record':
    Path('/etc/floppy/static-collection.json').write_text('{incomplete')

reusable = None
if helper.exists():
    reusable = subprocess.run([sys.executable, str(helper)], check=False).returncode == 0
    assert reusable == (case == 'normal'), (case, reusable)
command = subprocess.run([sys.executable, 'manage.py', 'collectstatic', '--noinput'],
                         capture_output=True, text=True, check=True)
files = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted(root.rglob('*')) if p.is_file()}
assert files['css/main.css'] == hashlib.sha256(source.read_bytes()).hexdigest()
if case == 'debug':
    assert any(name.startswith('debug_toolbar/') for name in files)
Path('/results/'+case+'.json').write_text(json.dumps(dict(
    case=case,reusable=reusable,stdout=command.stdout,stderr=command.stderr,files=files),indent=2)+'\n')
print(case, len(files), 'files; reuse', reusable)
