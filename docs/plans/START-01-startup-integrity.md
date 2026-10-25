# START-01 — Startup integrity and database file warming

- [ ] Complete START-01

Verdict: **INCONCLUSIVE**. No application implementation changed, and no speedup
is claimed. The locally maintained master backlog's START-01 entry is updated
with this result and remains open.

Full report, raw measurements, profiler evidence, commands and environment:
[`perf-results/start01/README.md`](../../perf-results/start01/README.md).
Machine-readable verdict:
[`decision.json`](../../perf-results/start01/decision.json).

The accepted baseline comprises 12 independent data-cold starts: three with
verification required and three with a valid recent verification, at each of
1,000 and 100,000 manually sourced tracked movies. All runs preserved library
counts, passed SQLite storage/foreign-key checks, and retained 564 migrations.
All 89 Linux integrity/recovery/watchdog tests passed.

The valid-record path already skips warming and the full scan. Required scans
warm one database-file length (7,639,040 or 441,847,808 bytes); subsequent SQLite
scans recorded no additional physical reads. Large-fixture warming cost
0.91–1.54 seconds and 0.60–0.95 CPU-seconds. This confirms a userspace pass,
not an unnecessary second physical disk pass or a safe end-to-end optimization.

The shared host had substantial changing load. No idle-host, five-repeat warm,
NAS/HDD, fragmented/free-page, nonempty-WAL startup or accepted-webhook queue
comparison was established. Removing warming could transfer I/O to SQLite and
change its read latency; that counterfactual remains unmeasured.

Before closing the item, separately scope paired alternating full-start trials
on representative isolated storage, preserving both integrity checks and
measuring first usability, memory and accepted-webhook queue latency. START-02
is not part of this result. No GitHub issue was created.
