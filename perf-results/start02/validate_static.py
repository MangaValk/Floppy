"""Compare real collectstatic output and exercise all cache fallback cases."""
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
for variant in ('baseline','changed'):
    output = root/'correctness'/variant
    output.mkdir(parents=True,exist_ok=True)
    cases = ['normal','debug','provider']
    if variant == 'changed':
        cases += ['missing-file','empty-root','changed-source','bad-record']
    for case in cases:
        result = subprocess.run(['docker','run','--rm','--network','none',
            '-e','SECRET=start02-static-fixture-only','-e','DEBUG=false',
            '-v',str(root)+':/bench:ro','-v',str(output)+':/results',
            '--entrypoint','python','floppy:start02-'+variant,'/bench/static_fixture.py',case],
            capture_output=True,text=True)
        (output/(case+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode == 0, result.stdout[-2000:]+result.stderr[-2000:]
        print(variant,case,'passed',flush=True)
for case in ('normal','debug','provider'):
    before = json.loads((root/'correctness/baseline'/(case+'.json')).read_text())
    after = json.loads((root/'correctness/changed'/(case+'.json')).read_text())
    assert before['files']==after['files'], case
reference = json.loads((root/'correctness/baseline/normal.json').read_text())['files']
for case in ('missing-file','empty-root','bad-record'):
    after = json.loads((root/'correctness/changed'/(case+'.json')).read_text())
    assert after['files']==reference, case
print('All static fallback and byte-for-byte comparisons passed.')
