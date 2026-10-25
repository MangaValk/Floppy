# START-02 — Repeated static collection, permissions and process bootstrap

- [ ] Complete START-02

Baseline and candidate each have 12 accepted cold starts: three per combination
of 1,000/100,000 tracked movies and required/recent SQLite verification.
Repeated work is confirmed: baseline starts collect 274 already-built,
unmodified static assets and recursively repair their ownership.

The isolated candidate validates a build-time static inventory and reuses
unchanged default-mode collection and ownership. All uncertain states retain
ordinary collection; custom UID/GID retain ownership repair. Integrity gates,
migration behavior, supervisor commands and process scheduling are unchanged.

Verdict: **INCONCLUSIVE** for full acceptance. Cold static interpreter CPU fell
3.249 → 0.205 seconds (-93.68%); warm CPU fell 2.438 → 0.269 (-88.98%). The
predeclared 80% static-stage target was exceeded, and the redundant collection
and default ownership repair disappeared. Five alternating warm pairs after
warmup show first-usable cohort medians 42.675 → 29.299 seconds, but the paired
randomization p-value is 0.1875 under changing shared-host load. This does not
establish an overall startup-latency improvement.

All 37 accepted startups preserved integrity, counts, migrations, assets and
authorization behavior; custom UID/GID ownership repair passed. Project-runner
groups passed 44 and 146 tests (14 macOS skips); all 102 Linux safety tests and
Ruff passed. Loaded application traffic, accepted-webhook latency and PostgreSQL
performance remain unmeasured. No speedup verdict is inferred from passing tests.

The candidate is committed on `codex/start02-bootstrap`, ending at
`9d460bc3523a51280fad55cf763845fbf9d784d3`, and preserved as a patch in the report.
It was not adopted into the shared checkout because full acceptance remains
unproven. Only this plan and benchmark evidence are committed there; unrelated
staged changes remain untouched. The locally ignored master tracker is updated
and remains unchecked.

Remaining validation is separately bounded: rerun the paired protocol on an
isolated representative host/storage with accepted-webhook queue latency and
matched idle/loaded application traffic before adopting the candidate or closing
the item. No GitHub issue was created.

Evidence, commands, environment, raw measurements and continuation history:

- [Report](../../perf-results/start02/README.md)
- [Work log](../../perf-results/start02/WORK_LOG.md)
- [Raw observations](../../perf-results/start02/raw-observations.md)
- [Machine-readable measurements](../../perf-results/start02/measurements.json)
- [Before/after deltas](../../perf-results/start02/comparison.md)
