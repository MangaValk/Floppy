# TASKS-04 baseline and after comparison

Lower is better for every column except the correctness invariants.

| Cell | Probe wait p95 s | Op wall mean s | Sync CPU total s | DB writes | Redis ops |
| --- | ---: | ---: | ---: | ---: | ---: |
| 100-cold-idle | 0.000 -> 0.000 | 1.50 -> 1.45 | 4.25 -> 4.12 | 370 -> 370 | 5563 -> 5556 |
| 100-cold-loaded | 2.002 -> 0.003 | 4.78 -> 1.93 | 4.34 -> 5.23 | 405 -> 487 | 5732 -> 6313 |
| 100-warm-idle | 0.000 -> 0.000 | 1.15 -> 1.15 | 2.94 -> 2.87 | 260 -> 260 | 2715 -> 2715 |
| 100-warm-loaded | 1.997 -> 0.002 | 4.81 -> 1.99 | 3.04 -> 3.75 | 295 -> 375 | 2925 -> 3460 |
| 10000-cold-idle | 0.000 -> 0.000 | 6.73 -> 6.19 | 27.55 -> 26.45 | 2460 -> 2460 | 58856 -> 58838 |
| 10000-cold-loaded | 1.861 -> 0.003 | 9.59 -> 6.68 | 27.47 -> 28.32 | 2495 -> 2575 | 59120 -> 59613 |
| 10000-warm-idle | 0.000 -> 0.000 | 6.08 -> 5.73 | 25.20 -> 24.04 | 2460 -> 2460 | 58723 -> 58705 |
| 10000-warm-loaded | 4.508 -> 0.003 | 8.20 -> 6.07 | 25.45 -> 25.60 | 2512 -> 2575 | 59043 -> 59479 |

## Idle window

| Metric | Baseline | After |
| --- | ---: | ---: |
| executions | 0 | 2 |
| cpu_s | 0.5682669999999987 | 0.4686230000000009 |
| executions_per_hour (after 300 s) | 0.0 | 0.0 |
| enqueues_per_hour (after 300 s) | 0.0 | 0.0 |
