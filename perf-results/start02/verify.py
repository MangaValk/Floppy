"""Check correctness invariants in every accepted startup artifact."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
reference = json.loads((root / 'correctness/baseline/normal.json').read_text())['files']
checked = []
for path in sorted((root / 'raw').glob('*/result.json')):
    result = json.loads(path.read_text())
    name = path.parent.name
    custom = name.startswith('changed-custom-uid-')
    after = name.startswith('changed-')
    assert result['healthy_s'] <= result['usable_s'] < 300, name
    correct = result['correctness']
    assert correct['quick_check'] == [['ok']] and not correct['foreign_key_check'], name
    assert correct['items'] == result['fixture']['items'], name
    assert correct['movies'] == result['fixture']['movies'], name
    assert correct['migrations'] == 564, name
    assert result['startup_status']['status'] == 'ok', name
    assert len(result['library_latency_s']) == len(result['webhook_rejection']) == 10, name
    assert all(row['status'] == 401 for row in result['webhook_rejection']), name
    assert {key: row['sha256'] for key, row in result['static_assets'].items()} == reference, name
    owner = (2001, 2002) if custom else (1000, 1000)
    assert all((row['uid'], row['gid']) == owner for row in result['static_assets'].values()), name
    stages = [json.loads(line) for line in (path.parent / 'stages.jsonl').read_text().splitlines()]
    scans = [row for row in stages if row['stage'] == '_scan_and_publish_block']
    warms = [row for row in stages if row['stage'] == '_warm_cache']
    if '-unverified-' in name:
        assert len(scans) == len(warms) == 1, name
    else:
        assert len(scans) == len(warms) == 0, name
    processes = [json.loads(line) for line in (path.parent / 'python-processes.jsonl').read_text().splitlines()]
    assert sum(row['label'] == 'collectstatic' for row in processes) == int(not after), name
    messages = [row['message'] for row in result['stages']]
    static_chown = any('Chowning /floppy/staticfiles' in message for message in messages)
    assert static_chown == (not after or custom), name
    assert result['sizing']['expected_programs'] == ['nginx', 'gunicorn', 'celery', 'celery-interactive'], name
    if '-warm-' in name or custom:
        assert result['interactive_queue_canary']['queue'] == 'interactive', name
    checked.append(name)
(root / 'correctness-summary.json').write_text(json.dumps(dict(accepted_count=len(checked), samples=checked, status='passed'), indent=2) + '\n')
print(f'{len(checked)} accepted starts passed all artifact invariants')
