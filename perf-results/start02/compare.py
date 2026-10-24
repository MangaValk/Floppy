"""Compare identical cohorts; retain observations rather than tail estimates."""
import json
import itertools
import statistics
from pathlib import Path

root = Path(__file__).resolve().parent
data = json.loads((root / 'measurements.json').read_text())
groups = {tuple(row['group']): row for row in data['summary']}
comparisons = []
lines = ['# Before/after cohort medians', '',
         'Lower is better for every metric below. Delta = changed minus baseline; '
         'percent = 100 × delta / baseline. Ordered cold cohorts are confounded by shared-host load. '
         'Warm trials alternate versions; trial zero is excluded.', '',
         '| Size / verification / cache | Metric | Baseline | Changed | Absolute delta | Percent |',
         '|---|---|---:|---:|---:|---:|']
for key, before in sorted(groups.items()):
    if key[0] != 'baseline' or ('changed', *key[1:]) not in groups:
        continue
    after = groups[('changed', *key[1:])]
    row = dict(cohort=list(key[1:]), baseline_n=before['n'], changed_n=after['n'], metrics={})
    for metric, value in before['median'].items():
        changed = after['median'][metric]
        delta = changed - value
        percent = 100 * delta / value if value else None
        row['metrics'][metric] = dict(baseline=value, changed=changed, delta=delta, percent=percent)
        lines.append(f"| {' / '.join(key[1:])} | {metric} | {value:.3f} | {changed:.3f} | {delta:+.3f} | {percent:+.2f}% |" if percent is not None else
                     f"| {' / '.join(key[1:])} | {metric} | {value:.3f} | {changed:.3f} | {delta:+.3f} | undefined |")
    comparisons.append(row)
stage_summary = {}
for variant in ('baseline', 'changed'):
    rows = [s for s in data['samples'] if s['variant'] == variant and not s['warmup']]
    cpu = [p['lifetime_cpu_s'] for s in rows for p in s['python_stages'] if p['label'] in ('collectstatic', 'static_check')]
    wall = [p['body_wall_s'] for s in rows for p in s['python_stages'] if p['label'] in ('collectstatic', 'static_check')]
    queue = [s['queue_roundtrip_ms'] for s in rows if s['queue_roundtrip_ms'] is not None]
    stage_summary[variant] = dict(static_cpu_s=cpu, static_wall_s=wall, queue_ms=queue,
                                  static_cpu_median_s=statistics.median(cpu) if cpu else None,
                                  queue_median_ms=statistics.median(queue) if queue else None)
paired = {}
warm = {variant: {s['index']: s for s in data['samples']
                 if s['variant'] == variant and s['cache'] == 'warm' and not s['warmup']}
        for variant in ('baseline', 'changed')}
indices = sorted(warm['baseline'].keys() & warm['changed'].keys())
if indices:
    for metric in ('healthy_s', 'usable_s', 'cpu_s', 'peak_mib', 'library_median_ms', 'webhook_median_ms', 'queue_roundtrip_ms'):
        deltas = [warm['changed'][i][metric] - warm['baseline'][i][metric] for i in indices]
        paired[metric] = dict(indices=indices, deltas=deltas, median_delta=statistics.median(deltas))
        if metric in ('healthy_s', 'usable_s'):
            # Exact sign-flip randomization of the mean paired difference.
            # With five pairs this is deliberately coarse, not a tail estimate.
            observed = abs(statistics.mean(deltas))
            permutations = [abs(statistics.mean(x * sign for x, sign in zip(deltas, signs)))
                            for signs in itertools.product((-1, 1), repeat=len(deltas))]
            paired[metric]['two_sided_sign_flip_p'] = sum(x >= observed - 1e-12 for x in permutations) / len(permutations)
(root / 'comparison.json').write_text(json.dumps(dict(cohorts=comparisons, stages=stage_summary, paired_warm=paired), indent=2) + '\n')
lines += ['', '## Alternating warm paired differences', '',
          'Pairs match trial indices; version order alternates. Positive means worse. '
          'Five pairs provide weak statistical resolution; randomization also assumes '
          'the within-pair host drift is exchangeable, which shared-host load can violate.', '',
          '| Metric | Raw changed-minus-baseline differences | Median difference |',
          '|---|---|---:|']
for metric, row in paired.items():
    lines.append(f"| {metric} | {', '.join(f'{x:+.3f}' for x in row['deltas'])} | {row['median_delta']:+.3f} |")
(root / 'comparison.md').write_text('\n'.join(lines) + '\n')
print(json.dumps(stage_summary, indent=2))
