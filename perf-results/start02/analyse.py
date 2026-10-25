"""Condense raw samples; report medians without inventing tail percentiles."""
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def cpu(snapshot):
    return int(dict(line.split() for line in snapshot['cpu.stat'].splitlines())['usage_usec']) / 1e6


def io(snapshot):
    totals = defaultdict(int)
    for line in snapshot['io.stat'].splitlines():
        for entry in line.split()[1:]:
            key, value = entry.split('=')
            totals[key] += int(value)
    return totals


def proc_io(value):
    return {key: int(count) for key, count in (line.split(':') for line in value.splitlines())}


samples = []
groups = defaultdict(list)
for path in sorted((ROOT/'raw').glob('*/result.json')):
    name = path.parent.name
    variant, size, verification, cache, index = name.rsplit('-', 4)
    result = json.loads(path.read_text())
    if 'usable_s' not in result:
        continue
    assert result['protocol'] == 'sequential-health-then-library-v2'
    end, start = result['ready_counters'], result['initial']
    endio, startio = io(end), io(start)
    sample = dict(name=name, variant=variant, size=size, verification=verification,
        cache=cache, index=int(index), warmup=cache == 'warm' and index == '0',
        healthy_s=result['healthy_s'], usable_s=result['usable_s'],
        cpu_s=cpu(end)-cpu(start), peak_mib=int(end['memory.peak'])/1048576,
        cpu_to_healthy_s=cpu(result['healthy_s_counters'])-cpu(start),
        peak_to_healthy_mib=int(result['healthy_s_counters']['memory.peak'])/1048576,
        disk_read_bytes=endio['rbytes']-startio['rbytes'],
        disk_write_bytes=endio['wbytes']-startio['wbytes'],
        disk_io_bytes=endio['rbytes']-startio['rbytes']+endio['wbytes']-startio['wbytes'],
        library_median_ms=statistics.median(result['library_latency_s'])*1000,
        webhook_median_ms=statistics.median(row['seconds'] for row in result['webhook_rejection'])*1000,
        correctness=result['correctness'], fixture=result['fixture'])
    sample['database_bytes_at_start'] = result['database_bytes_at_start']
    sample['host_loadavg_start'] = result.get('host_loadavg_start')
    sample['host_loadavg_ready'] = result.get('host_loadavg_ready')
    sample['asset_count'] = len(result['static_assets'])
    sample['asset_sha256'] = {name: item['sha256'] for name, item in result['static_assets'].items()}
    sample['queue_roundtrip_ms'] = result.get('interactive_queue_canary', {}).get('roundtrip_s')
    if sample['queue_roundtrip_ms'] is not None:
        sample['queue_roundtrip_ms'] *= 1000
    pp = path.parent/'python-processes.jsonl'
    sample['python_stages'] = [json.loads(line) for line in pp.read_text().splitlines()
        if json.loads(line)['label'] in ('collectstatic','static_check','resource_env','sizing_report')]
    stage_path = path.parent/'stages.jsonl'
    measured = [json.loads(line) for line in stage_path.read_text().splitlines()] if stage_path.exists() else []
    sample['policy_stages'] = []
    for stage in measured:
        before, after = proc_io(stage['io_before']), proc_io(stage['io_after'])
        sample['policy_stages'].append(dict(stage=stage['stage'],wall_s=stage['wall_s'],cpu_s=stage['cpu_s'],
            rchar=after['rchar']-before['rchar'],read_bytes=after['read_bytes']-before['read_bytes']))
    events = [dict(event, message=event['message'].replace('Preparing static files', 'Collecting static files'))
              for event in result['stages']]
    sample['ownership_stages'] = []
    ownership = [event for event in events if any(marker in event['message'] for marker in
        ('Chowning /floppy/staticfiles','Reusing image static ownership','Chowning /var/log/nginx','Chowning /var/lib/nginx','Starting services'))]
    for begin, finish in zip(ownership, ownership[1:]):
        a, b = io(begin['counters']), io(finish['counters'])
        sample['ownership_stages'].append(dict(stage=begin['message'],
            wall_s=finish['seconds']-begin['seconds'], cpu_s=cpu(finish['counters'])-cpu(begin['counters']),
            read_bytes=b['rbytes']-a['rbytes'],write_bytes=b['wbytes']-a['wbytes']))
    markers = ['Applying database migrations', 'Collecting static files', 'Fixing file ownership', 'Starting services']
    sample['startup_stages'] = []
    for left, right in zip(markers, markers[1:]):
        begin = next((event for event in events if left in event['message']), None)
        finish = next((event for event in events if right in event['message']), None)
        if begin and finish:
            begin_io, finish_io = io(begin['counters']), io(finish['counters'])
            sample['startup_stages'].append(dict(stage=left, wall_s=finish['seconds']-begin['seconds'],
                cpu_s=cpu(finish['counters'])-cpu(begin['counters']),
                read_bytes=finish_io['rbytes']-begin_io['rbytes'],
                write_bytes=finish_io['wbytes']-begin_io['wbytes']))
    samples.append(sample)
    if not sample['warmup']:
        groups[(variant, size, verification, cache)].append(sample)

metrics = ['healthy_s','usable_s','cpu_s','cpu_to_healthy_s','peak_mib','peak_to_healthy_mib','disk_read_bytes','disk_write_bytes','disk_io_bytes','library_median_ms','webhook_median_ms']
summary = []
for key, rows in sorted(groups.items()):
    summary.append(dict(group=list(key),n=len(rows),
        median={metric: statistics.median(row[metric] for row in rows) for metric in metrics},
        raw={metric: [row[metric] for row in rows] for metric in metrics}))
(ROOT/'measurements.json').write_text(json.dumps(dict(samples=samples,summary=summary), indent=2)+'\n')
print('| Variant | Size | Verification | Cache | n | Healthy s | Usable s | CPU s | Peak MiB | Disk read MiB |')
print('|---|---|---|---|---:|---:|---:|---:|---:|---:|')
for row in summary:
    med = row['median']
    print('| '+' | '.join(row['group'])+f" | {row['n']} | {med['healthy_s']:.3f} | {med['usable_s']:.3f} | {med['cpu_s']:.3f} | {med['peak_mib']:.1f} | {med['disk_read_bytes']/1048576:.1f} |")

lines = ['# Raw startup observations', '',
    'All times are seconds. Both versions use the same controlled workload; see comparison.md for cohort deltas.',
    'Lower latency, CPU, bytes and peak memory are better for an equivalent workload. No tail percentiles are estimated.', '',
    '| Sample | Healthy | Usable | CPU | Peak MiB | Disk read bytes | Disk write bytes |',
    '|---|---:|---:|---:|---:|---:|---:|']
for row in samples:
    lines.append(f"| {row['name']} | {row['healthy_s']:.6f} | {row['usable_s']:.6f} | {row['cpu_s']:.6f} | {row['peak_mib']:.3f} | {row['disk_read_bytes']} | {row['disk_write_bytes']} |")
lines += ['', '## Profiled integrity stages', '',
    '`rchar` includes small instrumentation reads; physical `read_bytes` is reported separately.', '',
    '| Sample | Stage | Wall s | CPU s | Logical bytes read | Physical bytes read |',
    '|---|---|---:|---:|---:|---:|']
for row in samples:
    for stage in row['policy_stages']:
        lines.append(f"| {row['name']} | {stage['stage']} | {stage['wall_s']:.6f} | {stage['cpu_s']:.6f} | {stage['rchar']} | {stage['read_bytes']} |")
lines += ['', '## Other startup stages', '',
    '| Sample | Stage | Wall s | CPU s | Block read bytes | Block write bytes |', '|---|---|---:|---:|---:|---:|']
for row in samples:
    for stage in row['startup_stages']:
        lines.append(f"| {row['name']} | {stage['stage']} | {stage['wall_s']:.6f} | {stage['cpu_s']:.6f} | {stage['read_bytes']} | {stage['write_bytes']} |")
lines += ['', '## Post-ready probes', '',
    'Each value is the within-start median of ten sequential requests. Application is otherwise idle, host is shared/loaded.', '',
    '| Sample | Library ms | Invalid-token webhook ms |', '|---|---:|---:|']
for row in samples:
    lines.append(f"| {row['name']} | {row['library_median_ms']:.3f} | {row['webhook_median_ms']:.3f} |")
(ROOT/'raw-observations.md').write_text('\n'.join(lines)+'\n')

extra = ['# Static and bootstrap stage observations', '',
    '| Sample | Python stage | Body wall s | Lifetime CPU s | Peak RSS KiB | Logical read bytes | Block read bytes | Block write bytes |',
    '|---|---|---:|---:|---:|---:|---:|---:|']
for row in samples:
    for stage in row['python_stages']:
        stage_io = proc_io(stage['io'])
        extra.append(f"| {row['name']} | {stage['label']} | {stage['body_wall_s']:.6f} | {stage['lifetime_cpu_s']:.6f} | {stage['maxrss_kib']} | {stage_io['rchar']} | {stage_io['read_bytes']} | {stage_io['write_bytes']} |")
extra += ['', '| Sample | Ownership stage | Wall s | CPU s | Read bytes | Written bytes |',
    '|---|---|---:|---:|---:|---:|']
for row in samples:
    for stage in row['ownership_stages']:
        extra.append(f"| {row['name']} | {stage['stage']} | {stage['wall_s']:.6f} | {stage['cpu_s']:.6f} | {stage['read_bytes']} | {stage['write_bytes']} |")
extra += ['', '| Sample | Interactive queue roundtrip ms |', '|---|---:|']
for row in samples:
    if row['queue_roundtrip_ms'] is not None:
        extra.append(f"| {row['name']} | {row['queue_roundtrip_ms']:.3f} |")
(ROOT/'static-stages.md').write_text('\n'.join(extra)+'\n')
