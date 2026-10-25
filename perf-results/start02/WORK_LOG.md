# Session work log

START-01 was committed as `d6292bdbe`; its tracked plan and local master tracker
remain open with an INCONCLUSIVE verdict. This session continued only START-02.

## Baseline before implementation

Built the exact d6292bdbe source archive and completed 12 disposable cold starts,
three per combination of small/large fixture and required/recent verification.
Six small baseline observations were available before editing implementation;
`target.json` records those observations and the explicit 80% static-stage CPU
reduction target. Remaining baseline trials completed before candidate timing.
The image already had 274 collected assets; every runtime collection reported
zero copied and 274 unmodified. The diagnostic profiler attributed collection
cost primarily to Django setup and imports. No production traffic was involved.

## Isolated candidate and validation

The shared checkout advanced through unrelated work. Candidate changes were
therefore committed in `/tmp/floppy-start02-worktree` at the baseline revision:

- `084171ee3`: static inventory validation, build record, conditional collection
  and default ownership reuse, regression tests.
- `4792c24d6`: direct recorder project import path, discovered by image build.
- `9d460bc35`: replace rather than prepend the script directory, preventing
  `config/celery.py` from shadowing the Celery package in the build recorder.

The final image builds and validates its record. All ten real-image static
correctness cases pass: baseline/candidate normal, debug and provider modes;
candidate missing output file, empty output, changed source and corrupt record.
Normal/debug/provider inventories compare byte for byte across versions.
Both missing-output cases and invalid-record fallback restore baseline bytes.

Project runner: 44 static/bootstrap/path/CSS tests passed; 146 integrity/recovery/
runtime/preflight tests passed with 14 platform skips. Ruff across src passed.
The first additional minimal-settings Linux invocation failed: STATIC_URL was
missing for the new static suite, and importing tests from the production layout
gave one source-layout shell fixture an incorrect subprocess path. This is a test
invocation issue, retained as diagnostic evidence; `linux_tests.py` supplies the
missing setting and must run from the mounted source's src directory.

## Interruption and resumption

All 12 candidate cold starts completed before the rate-limit interruption.
Warm trial zero stopped on a canary assertion after Celery successfully completed
the task: its accumulate result is a sequence, not a scalar. The rejected run is
retained under `rejected-warm-canary/`, excluded from accepted results. The harness
now compares the returned sequence and exposes subprocess diagnostics. Primary
cold measurements and application code were unaffected. Alternating warm trials
were resumed with one warmup and five accepted trials per version, followed by a
custom UID/GID startup. No prior cold results were overwritten.

All commands, results and final limitations are summarized in README.md;
measurements.json, comparison.json and raw/ preserve machine-readable readings.

## Final disposition

All 37 accepted starts passed the artifact verifier, including custom UID/GID
2001/2002. The corrected Linux command passed all 102 tests in 23.836 seconds.
The final static CPU reductions are 93.68% cold and 88.98% warm. Five paired
warm readiness observations have two-sided sign-flip p=0.1875. The overall
verdict is INCONCLUSIVE; the candidate is retained in its isolated committed
branch and patch, not adopted into the shared checkout. The report and tracked
START-02 plan are committed separately from unrelated staged work. The master
backlog is locally ignored and was updated without force-adding it.
