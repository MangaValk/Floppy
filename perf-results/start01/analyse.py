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
    stage_path = path.parent/'stages.jsonl'
    measured = [json.loads(line) for line in stage_path.read_text().splitlines()] if stage_path.exists() else []
    sample['policy_stages'] = []
    for stage in measured:
        before, after = proc_io(stage['io_before']), proc_io(stage['io_after'])
        sample['policy_stages'].append(dict(stage=stage['stage'],wall_s=stage['wall_s'],cpu_s=stage['cpu_s'],
            rchar=after['rchar']-before['rchar'],read_bytes=after['read_bytes']-before['read_bytes']))
    events = result['stages']
    markers = ['Applying database migrations', 'Collecting static files', 'Fixing file ownership', 'Starting services']
    sample['startup_stages'] = []
    for left, right in zip(markers, markers[1:]):
        begin = next((event for event in events if left in event['message']), None)
        finish = next((event for event in events if right in event['message']), None)
        if begin and finish:
            sample['startup_stages'].append(dict(stage=left, wall_s=finish['seconds']-begin['seconds'],
                cpu_s=cpu(finish['counters'])-cpu(begin['counters'])))
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
    'All times are seconds. These are baseline conditions, not before/after optimization deltas.',
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
    '| Sample | Stage | Wall s | CPU s |', '|---|---|---:|---:|']
for row in samples:
    for stage in row['startup_stages']:
        lines.append(f"| {row['name']} | {stage['stage']} | {stage['wall_s']:.6f} | {stage['cpu_s']:.6f} |")
lines += ['', '## Post-ready probes', '',
    'Each value is the within-start median of ten sequential requests. Application is otherwise idle, host is shared/loaded.', '',
    '| Sample | Library ms | Invalid-token webhook ms |', '|---|---:|---:|']
for row in samples:
    lines.append(f"| {row['name']} | {row['library_median_ms']:.3f} | {row['webhook_median_ms']:.3f} |")
(ROOT/'raw-observations.md').write_text('\n'.join(lines)+'\n')
