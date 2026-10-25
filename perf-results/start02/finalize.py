"""Write the conservative acceptance decision from the preserved observations."""
import json
import statistics
from pathlib import Path

root = Path(__file__).resolve().parent
data = json.loads((root / 'measurements.json').read_text())
comparison = json.loads((root / 'comparison.json').read_text())
stage = {}
for cache in ('cold', 'warm'):
    stage[cache] = {}
    for variant in ('baseline', 'changed'):
        samples = [r for r in data['samples'] if r['variant'] == variant and r['cache'] == cache and not r['warmup']]
        processes = [p for r in samples for p in r['python_stages'] if p['label'] in ('static_check', 'collectstatic')]
        ownership = [p for r in samples for p in r['ownership_stages'] if 'static' in p['stage']]
        stage[cache][variant] = dict(
            n=len(samples),
            static_cpu_s=statistics.median(p['lifetime_cpu_s'] for p in processes),
            static_wall_s=statistics.median(p['body_wall_s'] for p in processes),
            static_cpu_raw_s=[p['lifetime_cpu_s'] for p in processes],
            ownership_median={key: statistics.median(p[key] for p in ownership)
                              for key in ('wall_s', 'cpu_s', 'read_bytes', 'write_bytes')},
        )
decision = dict(
    verdict='INCONCLUSIVE', checklist_complete=False, application_change_adopted=False,
    problem_confirmed=True, baseline_sha='d6292bdbe0281b68057b485bfff1601139f40057',
    candidate_sha='9d460bc3523a51280fad55cf763845fbf9d784d3',
    candidate_branch='codex/start02-bootstrap',
    candidate_files=['Dockerfile', 'entrypoint.sh', 'src/config/static_collection.py',
                     'src/config/tests/test_static_collection.py', 'src/app/tests/test_data_paths.py'],
    confirmed='Repeated 274-file collection and default recursive static ownership repair removed; static CPU target exceeded.',
    acceptance_limit='End-to-end readiness is not statistically isolated from changing shared-host load; accepted webhook and loaded-application latency were not measured.',
    stage_medians=stage, paired_warm=comparison['paired_warm'],
    retained='Candidate commits and candidate.patch.gz are reviewable; no candidate runtime changes adopted into the shared checkout.',
)
(root / 'decision.json').write_text(json.dumps(decision, indent=2) + '\n')
lines = ['## Final measurements and acceptance', '',
         '**Verdict: INCONCLUSIVE for the full START-02 acceptance criteria.** The redundant '
         'work and its CPU cost are confirmed; the bounded candidate beats its static-stage '
         'target. End-to-end startup improvement is not statistically established on this '
         'changing shared host. START-02 remains unchecked. Candidate implementation is '
         'committed on `codex/start02-bootstrap` and preserved as `candidate.patch.gz`; it is '
         'not adopted into the shared checkout. Unrelated staged work is preserved.', '',
         'There are 24 accepted cold starts, ten accepted alternating warm observations '
         'after two warmups, and one custom-UID correctness startup: 37 successful starts. '
         'The rejected canary warmup is retained separately and excluded.', '',
         '### Static work (lower is better)', '',
         '| Cache | Metric | Baseline median | Candidate median | Absolute delta | Percent |',
         '|---|---|---:|---:|---:|---:|']
for cache, variants in stage.items():
    before, after = variants['baseline'], variants['changed']
    for metric in ('static_cpu_s', 'static_wall_s'):
        delta = after[metric] - before[metric]
        lines.append(f'| {cache} | {metric} | {before[metric]:.6f} | {after[metric]:.6f} | {delta:+.6f} | {100 * delta / before[metric]:+.2f}% |')
lines += ['', 'Default-mode runtime full collections fall from one to zero and recursive '
          'static chowns from one to zero on every accepted candidate start. Warmup '
          'filesystem diffs show 305 changed collected-static paths before and zero after. '
          'Cold ownership-stage medians fall from 1.992 wall seconds / 0.237 CPU-seconds '
          'to 0.0015 / 0.0015, with associated reads/writes from 8,196,096 / 8,073,216 '
          'bytes to zero. These are stage-associated cgroup observations, not a block-level '
          'proof of filesystem copy-up causality. The separate cProfile diagnostics show '
          'baseline Django setup/imports versus metadata traversal in the candidate.', '',
          '### Raw health / first-usable observations (seconds)', '',
          'Every CPU, memory, I/O and latency reading is also in '
          '[raw-observations.md](raw-observations.md) and [measurements.json](measurements.json). '
          'All absolute and percentage cohort deltas are in [comparison.md](comparison.md) '
          'and [comparison.json](comparison.json). Lower is better.', '',
          '| Version / size / verification / cache | n | Healthy raw | First usable raw |',
          '|---|---:|---|---|']
for group in data['summary']:
    if group['group'][0] not in ('baseline', 'changed'):
        continue
    lines.append('| ' + ' / '.join(group['group']) + f" | {group['n']} | " +
                 ', '.join(f'{x:.3f}' for x in group['raw']['healthy_s']) + ' | ' +
                 ', '.join(f'{x:.3f}' for x in group['raw']['usable_s']) + ' |')
lines += ['', '### Interpretation and side effects', '',
          'Alternating warm cohort medians: healthy 40.776 → 27.809 seconds '
          '(-12.967, -31.80%); first usable 42.675 → 29.299 (-13.376, -31.34%); '
          'CPU through usability 36.296 → 29.276 (-7.020, -19.34%); total block I/O '
          '87,515,136 → 53,227,520 bytes (-34,287,616, -39.18%); peak through usability '
          '558.781 → 543.230 MiB (-15.551, -2.78%). These observations are not all '
          'attributable to static collection: host load and worker initialization overlap vary.', '',
          'The five paired first-usable differences are -10.766, +7.611, -16.594, '
          '-20.878 and -0.542 seconds. The exact two-sided sign-flip p-value is 0.1875 '
          '(same for health); five pairs and nonstationary host load do not establish '
          'a statistically reliable overall latency gain. The small/unverified cold '
          'cohort is slower by 9.120 seconds (+24.82%) at its median, while other cold '
          'cohorts are faster; ordered cohort differences cannot identify the cause.', '',
          'Post-ready warm library median is 469.588 → 291.814 ms (-37.86%); rejected '
          'webhook median 10.523 → 5.419 ms (-48.50%). Interactive queue round-trip '
          'cohort medians are 426.918 → 437.593 ms (+10.675, +2.50%); the paired '
          'median difference is -124.543 ms. Peak at the earlier health milestone rises '
          '492.730 → 518.570 MiB (+25.840, +5.24%), although peak through usability falls. '
          'No consistent resource/queue regression is established, but absence of '
          'regression under accepted webhooks or application load remains unproven. '
          'Large/verified cold disk reads also rise; total I/O is not uniformly lower.', '',
          'Cold means data-cache eviction only; warm means data warmed. Both fixture '
          'sizes have the same 274 real assets. No static-file-count scaling, same-container '
          'restart timing, isolated-host, loaded-application, PostgreSQL performance or '
          'accepted-webhook workload was measured. Ordinary PostgreSQL startup still '
          'uses the same collection/fallback path; this candidate does not touch database code.', '',
          '### Correctness, files and rollback', '',
          'See correctness-summary.json for every accepted-start invariant and '
          'correctness/ for real-image fallback and byte comparisons. The final Linux '
          'safety test output and project-runner logs are retained with the artifacts. '
          'No passing test is treated as performance evidence.', '',
          'Candidate files: Dockerfile; entrypoint.sh; src/config/static_collection.py; '
          'src/config/tests/test_static_collection.py; src/app/tests/test_data_paths.py. '
          'Shared-checkout changes for this task are the benchmark/report under '
          'perf-results/start02/ and docs/plans/START-02-static-bootstrap.md. The locally '
          'ignored master backlog was updated without force-adding it or other private plans.', '',
          'Rollback: the current application needs no rollback because the candidate was '
          'not adopted. Discard a candidate deployment by running the baseline image. '
          'If adopting the patch later, reverting its entrypoint/Dockerfile changes and '
          'removing the helper restores unconditional collection and static ownership repair; '
          'no database/schema/data rollback is involved.', '',
          'Separately scoped remaining validation: repeat the same paired protocol on '
          'an isolated representative host/storage, with accepted-webhook queue latency '
          'and matched idle/loaded application traffic, before adopting the candidate and '
          'closing START-02. No GitHub issue was created.']
base = (root / 'README.md').read_text().split('## Final measurements and acceptance')[0]
base = base.replace('Measurement in progress; the tracker remains open until the final comparison.',
                    'The repeated work is confirmed. Full acceptance is **INCONCLUSIVE**; START-02 remains open. See the final comparison below.')
(root / 'README.md').write_text(base + '\n' + '\n'.join(lines) + '\n')
