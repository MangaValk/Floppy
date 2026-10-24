# TASKS-05 measurements

All deltas are after minus baseline; lower is better for work, CPU, delay and memory.
Warmup excluded unless noted. Raw observations and metric definitions are in `measurements.json` and `*.jsonl`.
Wall, CPU and latency deltas on ordinary sync trials are not attributable to this change: the two phases ran at different points on a shared host and identical-work trials moved by tens of percent. The deterministic enqueue, execution, statement and Redis-command counts are the evidence; the backlog phase is the target workload.

## tasks05-100-warm-quiet

| Metric | Baseline median | After median | Absolute delta | Change |
|---|---:|---:|---:|---:|
| sync_enqueues | 1 | 1 | +0 | +0.00% |
| task_executions | 1 | 1 | +0 | +0.00% |
| unproductive_syncs | 0 | 0 | +0 | undefined (zero baseline) |
| wall_s | 0.712197 | 0.374812 | -0.337385 | -47.37% |
| sync_runtime_total_s | 0.487214 | 0.203068 | -0.284145 | -58.32% |
| worker_cpu_s | 0.44523 | 0.195593 | -0.249637 | -56.07% |
| container_cpu_s | 0.528386 | 0.217356 | -0.31103 | -58.86% |
| db_write_statements | 26 | 26 | +0 | +0.00% |
| redis_commands_parent_and_task_bodies | 135 | 137 | +2 | +1.48% |
| queue_wait_p50_s | 0.00760984 | 0.0027473 | -0.00486255 | -63.90% |
| queue_wait_empirical_p95_s | 0.00760984 | 0.0027473 | -0.00486255 | -63.90% |
| peak_pss_bytes | 3.48605e+08 | 3.48024e+08 | -581632 | -0.17% |
| peak_uss_bytes | 2.87986e+08 | 2.86994e+08 | -991232 | -0.34% |
| container_memory_peak_cumulative_bytes | 4.32583e+08 | 4.03362e+08 | -2.92209e+07 | -6.75% |

## tasks05-100-warm-playback

| Metric | Baseline median | After median | Absolute delta | Change |
|---|---:|---:|---:|---:|
| sync_enqueues | 3 | 3 | +0 | +0.00% |
| task_executions | 6 | 6 | +0 | +0.00% |
| unproductive_syncs | 2 | 2 | +0 | +0.00% |
| wall_s | 0.804841 | 0.532369 | -0.272472 | -33.85% |
| sync_runtime_total_s | 0.440494 | 0.274052 | -0.166442 | -37.79% |
| worker_cpu_s | 0.544312 | 0.337922 | -0.20639 | -37.92% |
| container_cpu_s | 0.634004 | 0.375876 | -0.258128 | -40.71% |
| db_write_statements | 46 | 46 | +0 | +0.00% |
| redis_commands_parent_and_task_bodies | 276 | 283 | +7 | +2.54% |
| queue_wait_p50_s | 0.101653 | 0.0549479 | -0.0467048 | -45.95% |
| queue_wait_empirical_p95_s | 0.477228 | 0.306775 | -0.170453 | -35.72% |
| webhook_delay_p50_s | 0.0787277 | 0.0395927 | -0.039135 | -49.71% |
| webhook_delay_empirical_p95_s | 0.122089 | 0.0681651 | -0.0539238 | -44.17% |
| peak_pss_bytes | 3.49465e+08 | 3.51072e+08 | +1.60768e+06 | +0.46% |
| peak_uss_bytes | 2.8969e+08 | 2.91119e+08 | +1.4295e+06 | +0.49% |
| container_memory_peak_cumulative_bytes | 4.32583e+08 | 4.03362e+08 | -2.92209e+07 | -6.75% |

## tasks05-100-cold-quiet

| Metric | Baseline median | After median | Absolute delta | Change |
|---|---:|---:|---:|---:|
| sync_enqueues | 1 | 1 | +0 | +0.00% |
| task_executions | 1 | 1 | +0 | +0.00% |
| unproductive_syncs | 0 | 0 | +0 | undefined (zero baseline) |
| wall_s | 0.657761 | 0.424883 | -0.232878 | -35.40% |
| sync_runtime_total_s | 0.44309 | 0.21382 | -0.22927 | -51.74% |
| worker_cpu_s | 0.416656 | 0.205566 | -0.21109 | -50.66% |
| container_cpu_s | 0.495943 | 0.228253 | -0.26769 | -53.98% |
| db_write_statements | 30 | 30 | +0 | +0.00% |
| redis_commands_parent_and_task_bodies | 149 | 151 | +2 | +1.34% |
| queue_wait_p50_s | 0.0149286 | 0.00286937 | -0.0120592 | -80.78% |
| queue_wait_empirical_p95_s | 0.0149286 | 0.00286937 | -0.0120592 | -80.78% |
| peak_pss_bytes | 3.49723e+08 | 3.51113e+08 | +1.39059e+06 | +0.40% |
| peak_uss_bytes | 2.89948e+08 | 2.9116e+08 | +1.21242e+06 | +0.42% |
| container_memory_peak_cumulative_bytes | 4.32583e+08 | 4.03362e+08 | -2.92209e+07 | -6.75% |

## tasks05-100-cold-playback

| Metric | Baseline median | After median | Absolute delta | Change |
|---|---:|---:|---:|---:|
| sync_enqueues | 3 | 3 | +0 | +0.00% |
| task_executions | 6 | 6 | +0 | +0.00% |
| unproductive_syncs | 2 | 2 | +0 | +0.00% |
| wall_s | 0.807342 | 0.525246 | -0.282096 | -34.94% |
| sync_runtime_total_s | 0.451854 | 0.247278 | -0.204575 | -45.27% |
| worker_cpu_s | 0.56586 | 0.308484 | -0.257376 | -45.48% |
| container_cpu_s | 0.659241 | 0.344124 | -0.315117 | -47.80% |
| db_write_statements | 50 | 50 | +0 | +0.00% |
| redis_commands_parent_and_task_bodies | 290 | 297 | +7 | +2.41% |
| queue_wait_p50_s | 0.0949694 | 0.0552629 | -0.0397065 | -41.81% |
| queue_wait_empirical_p95_s | 0.492624 | 0.272875 | -0.219749 | -44.61% |
| webhook_delay_p50_s | 0.072674 | 0.0416205 | -0.0310535 | -42.73% |
| webhook_delay_empirical_p95_s | 0.11824 | 0.0686731 | -0.0495665 | -41.92% |
| peak_pss_bytes | 3.49125e+08 | 3.50556e+08 | +1.43155e+06 | +0.41% |
| peak_uss_bytes | 2.89354e+08 | 2.90607e+08 | +1.25338e+06 | +0.43% |
| container_memory_peak_cumulative_bytes | 4.32583e+08 | 4.03362e+08 | -2.92209e+07 | -6.75% |

## tasks05-12000-warm-quiet

| Metric | Baseline median | After median | Absolute delta | Change |
|---|---:|---:|---:|---:|
| sync_enqueues | 1 | 1 | +0 | +0.00% |
| task_executions | 1 | 1 | +0 | +0.00% |
| unproductive_syncs | 0 | 0 | +0 | undefined (zero baseline) |
| wall_s | 3.49058 | 2.07827 | -1.41231 | -40.46% |
| sync_runtime_total_s | 3.26506 | 1.8828 | -1.38226 | -42.33% |
| worker_cpu_s | 3.20583 | 1.86519 | -1.34064 | -41.82% |
| container_cpu_s | 3.47294 | 1.94892 | -1.52401 | -43.88% |
| db_write_statements | 26 | 26 | +0 | +0.00% |
| redis_commands_parent_and_task_bodies | 135 | 137 | +2 | +1.48% |
| queue_wait_p50_s | 0.014493 | 0.00357938 | -0.0109136 | -75.30% |
| queue_wait_empirical_p95_s | 0.014493 | 0.00357938 | -0.0109136 | -75.30% |
| peak_pss_bytes | 3.71407e+08 | 3.72691e+08 | +1.2841e+06 | +0.35% |
| peak_uss_bytes | 3.11636e+08 | 3.12742e+08 | +1.10592e+06 | +0.35% |
| container_memory_peak_cumulative_bytes | 4.32583e+08 | 4.03362e+08 | -2.92209e+07 | -6.75% |

## tasks05-12000-warm-playback

| Metric | Baseline median | After median | Absolute delta | Change |
|---|---:|---:|---:|---:|
| sync_enqueues | 3 | 3 | +0 | +0.00% |
| task_executions | 6 | 6 | +0 | +0.00% |
| unproductive_syncs | 2 | 2 | +0 | +0.00% |
| wall_s | 4.36525 | 2.47732 | -1.88793 | -43.25% |
| sync_runtime_total_s | 3.85483 | 2.09311 | -1.76172 | -45.70% |
| worker_cpu_s | 3.95041 | 2.2147 | -1.7357 | -43.94% |
| container_cpu_s | 4.38865 | 2.32984 | -2.05881 | -46.91% |
| db_write_statements | 46 | 46 | +0 | +0.00% |
| redis_commands_parent_and_task_bodies | 276 | 283 | +7 | +2.54% |
| queue_wait_p50_s | 0.163745 | 0.0686439 | -0.0951014 | -58.08% |
| queue_wait_empirical_p95_s | 3.65466 | 2.03899 | -1.61568 | -44.21% |
| webhook_delay_p50_s | 0.13743 | 0.0537522 | -0.083678 | -60.89% |
| webhook_delay_empirical_p95_s | 0.19006 | 0.0836976 | -0.106363 | -55.96% |
| peak_pss_bytes | 3.71976e+08 | 3.72908e+08 | +931840 | +0.25% |
| peak_uss_bytes | 3.12205e+08 | 3.12959e+08 | +753664 | +0.24% |
| container_memory_peak_cumulative_bytes | 4.32583e+08 | 4.03362e+08 | -2.92209e+07 | -6.75% |

## tasks05-12000-cold-quiet

| Metric | Baseline median | After median | Absolute delta | Change |
|---|---:|---:|---:|---:|
| sync_enqueues | 1 | 1 | +0 | +0.00% |
| task_executions | 1 | 1 | +0 | +0.00% |
| unproductive_syncs | 0 | 0 | +0 | undefined (zero baseline) |
| wall_s | 4.6544 | 2.50528 | -2.14912 | -46.17% |
| sync_runtime_total_s | 4.4199 | 2.32228 | -2.09762 | -47.46% |
| worker_cpu_s | 4.34374 | 2.30324 | -2.0405 | -46.98% |
| container_cpu_s | 4.70326 | 2.39951 | -2.30374 | -48.98% |
| db_write_statements | 30 | 30 | +0 | +0.00% |
| redis_commands_parent_and_task_bodies | 149 | 151 | +2 | +1.34% |
| queue_wait_p50_s | 0.0223832 | 0.00629592 | -0.0160873 | -71.87% |
| queue_wait_empirical_p95_s | 0.0223832 | 0.00629592 | -0.0160873 | -71.87% |
| peak_pss_bytes | 3.74669e+08 | 3.74895e+08 | +225280 | +0.06% |
| peak_uss_bytes | 3.14966e+08 | 3.14946e+08 | -20480 | -0.01% |
| container_memory_peak_cumulative_bytes | 4.32583e+08 | 4.03362e+08 | -2.92209e+07 | -6.75% |

## tasks05-12000-cold-playback

| Metric | Baseline median | After median | Absolute delta | Change |
|---|---:|---:|---:|---:|
| sync_enqueues | 3 | 3 | +0 | +0.00% |
| task_executions | 6 | 6 | +0 | +0.00% |
| unproductive_syncs | 2 | 2 | +0 | +0.00% |
| wall_s | 3.07207 | 2.84423 | -0.227849 | -7.42% |
| sync_runtime_total_s | 2.71064 | 2.51881 | -0.191831 | -7.08% |
| worker_cpu_s | 2.78461 | 2.60209 | -0.182519 | -6.55% |
| container_cpu_s | 2.94944 | 2.73262 | -0.216826 | -7.35% |
| db_write_statements | 50 | 50 | +0 | +0.00% |
| redis_commands_parent_and_task_bodies | 290 | 297 | +7 | +2.41% |
| queue_wait_p50_s | 0.0773801 | 0.0672855 | -0.0100945 | -13.05% |
| queue_wait_empirical_p95_s | 2.60988 | 2.42925 | -0.180634 | -6.92% |
| webhook_delay_p50_s | 0.0613668 | 0.0517564 | -0.00961041 | -15.66% |
| webhook_delay_empirical_p95_s | 0.0999444 | 0.0828147 | -0.0171297 | -17.14% |
| peak_pss_bytes | 3.77283e+08 | 3.7736e+08 | +77824 | +0.02% |
| peak_uss_bytes | 3.17579e+08 | 3.17411e+08 | -167936 | -0.05% |
| container_memory_peak_cumulative_bytes | 4.32583e+08 | 4.06176e+08 | -2.64069e+07 | -6.10% |

## reconcile-backlog

| Metric | Baseline median | After median | Absolute delta | Change |
|---|---:|---:|---:|---:|
| sync_enqueues | 3 | 1 | -2 | -66.67% |
| task_executions | 7 | 5 | -2 | -28.57% |
| unproductive_syncs | 2 | 0 | -2 | -100.00% |
| wall_s | 6.37967 | 6.03086 | -0.348809 | -5.47% |
| sync_runtime_total_s | 5.14493 | 4.75488 | -0.390048 | -7.58% |
| worker_cpu_s | 5.12906 | 4.74373 | -0.385327 | -7.51% |
| container_cpu_s | 5.47497 | 5.07413 | -0.400834 | -7.32% |
| db_write_statements | 54 | 44 | -10 | -18.52% |
| redis_commands_parent_and_task_bodies | 325 | 282 | -43 | -13.23% |
| queue_wait_p50_s | 0.966351 | 0.954785 | -0.0115657 | -1.20% |
| queue_wait_empirical_p95_s | 4.99579 | 0.980497 | -4.0153 | -80.37% |
| peak_pss_bytes | 3.85331e+08 | 3.85536e+08 | +204800 | +0.05% |
| peak_uss_bytes | 3.25628e+08 | 3.25591e+08 | -36864 | -0.01% |
| container_memory_peak_cumulative_bytes | 4.32583e+08 | 4.13344e+08 | -1.92389e+07 | -4.45% |

## failure-and-retry

| Metric | Baseline median | After median | Absolute delta | Change |
|---|---:|---:|---:|---:|
| sync_enqueues | 2 | 2 | +0 | +0.00% |
| task_executions | 3 | 3 | +0 | +0.00% |
| unproductive_syncs | 0 | 0 | +0 | undefined (zero baseline) |
| wall_s | 11.4374 | 11.4367 | -0.000684917 | -0.01% |
| sync_runtime_total_s | 4.97368 | 4.94656 | -0.0271215 | -0.55% |
| worker_cpu_s | 4.95524 | 4.9263 | -0.0289484 | -0.58% |
| container_cpu_s | 5.48963 | 5.44873 | -0.040902 | -0.75% |
| db_write_statements | 48 | 48 | +0 | +0.00% |
| redis_commands_parent_and_task_bodies | 286 | 289 | +3 | +1.05% |
| queue_wait_p50_s | 0.00943375 | 0.00838542 | -0.00104833 | -11.11% |
| queue_wait_empirical_p95_s | 0.0112457 | 0.0212126 | +0.00996685 | +88.63% |
| peak_pss_bytes | 3.90119e+08 | 3.87473e+08 | -2.64602e+06 | -0.68% |
| peak_uss_bytes | 3.30531e+08 | 3.27639e+08 | -2.89178e+06 | -0.87% |
| container_memory_peak_cumulative_bytes | 4.32583e+08 | 4.1599e+08 | -1.65929e+07 | -3.84% |

## idempotency

| Metric | Baseline median | After median | Absolute delta | Change |
|---|---:|---:|---:|---:|
| sync_enqueues | 2 | 2 | +0 | +0.00% |
| task_executions | 2 | 2 | +0 | +0.00% |
| unproductive_syncs | 2 | 2 | +0 | +0.00% |
| wall_s | 1.20876 | 0.749076 | -0.459682 | -38.03% |
| sync_runtime_total_s | 0.949709 | 0.55707 | -0.392639 | -41.34% |
| worker_cpu_s | 0.932178 | 0.547511 | -0.384667 | -41.27% |
| container_cpu_s | 1.07058 | 0.595678 | -0.474898 | -44.36% |
| db_write_statements | 10 | 10 | +0 | +0.00% |
| redis_commands_parent_and_task_bodies | 48 | 50 | +2 | +4.17% |
| queue_wait_p50_s | 0.365371 | 0.19933 | -0.166042 | -45.44% |
| queue_wait_empirical_p95_s | 0.697679 | 0.391714 | -0.305965 | -43.85% |
| peak_pss_bytes | 3.68939e+08 | 3.6828e+08 | -659456 | -0.18% |
| peak_uss_bytes | 3.09424e+08 | 3.0865e+08 | -774144 | -0.25% |
| container_memory_peak_cumulative_bytes | 4.32583e+08 | 4.1599e+08 | -1.65929e+07 | -3.84% |

## settle

| Metric | Baseline median | After median | Absolute delta | Change |
|---|---:|---:|---:|---:|
| sync_enqueues | 0 | 0 | +0 | undefined (zero baseline) |
| task_executions | 1 | 1 | +0 | +0.00% |
| unproductive_syncs | 0 | 0 | +0 | undefined (zero baseline) |
| wall_s | 0.295513 | 0.240293 | -0.05522 | -18.69% |
| sync_runtime_total_s | 0 | 0 | +0 | undefined (zero baseline) |
| worker_cpu_s | 0.0425925 | 0.0319623 | -0.0106302 | -24.96% |
| container_cpu_s | 0.176561 | 0.13308 | -0.043481 | -24.63% |
| db_write_statements | 0 | 0 | +0 | undefined (zero baseline) |
| redis_commands_parent_and_task_bodies | 1 | 1 | +0 | +0.00% |
| queue_wait_p50_s | 0.0356581 | 0.0235281 | -0.01213 | -34.02% |
| queue_wait_empirical_p95_s | 0.0356581 | 0.0235281 | -0.01213 | -34.02% |
| peak_pss_bytes | 3.66043e+08 | 3.65535e+08 | -507904 | -0.14% |
| peak_uss_bytes | 3.06688e+08 | 3.05922e+08 | -765952 | -0.25% |
| container_memory_peak_cumulative_bytes | 4.32583e+08 | 4.1599e+08 | -1.65929e+07 | -3.84% |

## idle-1800s

| Metric | Baseline median | After median | Absolute delta | Change |
|---|---:|---:|---:|---:|
| sync_enqueues | 0 | 0 | +0 | undefined (zero baseline) |
| task_executions | 30 | 30 | +0 | +0.00% |
| unproductive_syncs | 0 | 0 | +0 | undefined (zero baseline) |
| wall_s | 1800.23 | 1800.24 | +0.0111609 | +0.00% |
| sync_runtime_total_s | 0 | 0 | +0 | undefined (zero baseline) |
| worker_cpu_s | 1.24602 | 0.94821 | -0.297811 | -23.90% |
| container_cpu_s | 15.7114 | 13.228 | -2.48342 | -15.81% |
| db_write_statements | 0 | 0 | +0 | undefined (zero baseline) |
| redis_commands_parent_and_task_bodies | 30 | 30 | +0 | +0.00% |
| queue_wait_p50_s | 0.0242572 | 0.0205002 | -0.003757 | -15.49% |
| queue_wait_empirical_p95_s | 0.0546312 | 0.111688 | +0.0570569 | +104.44% |
| peak_pss_bytes | 3.68873e+08 | 3.65855e+08 | -3.01875e+06 | -0.82% |
| peak_uss_bytes | 3.11448e+08 | 3.067e+08 | -4.74726e+06 | -1.52% |
| container_memory_peak_cumulative_bytes | 4.32583e+08 | 4.1599e+08 | -1.65929e+07 | -3.84% |

## reconcile-backlog-first-tick

| Metric | Baseline median | After median | Absolute delta | Change |
|---|---:|---:|---:|---:|
| sync_enqueues | 6 | 2 | -4 | -66.67% |
| task_executions | 10 | 6 | -4 | -40.00% |
| unproductive_syncs | 4 | 0 | -4 | -100.00% |
| wall_s | 131.028 | 130.996 | -0.0320627 | -0.02% |
| sync_runtime_total_s | 5.69536 | 5.686 | -0.00935483 | -0.16% |
| worker_cpu_s | 5.71933 | 5.687 | -0.0323288 | -0.57% |
| container_cpu_s | 11.0621 | 10.7452 | -0.316916 | -2.86% |
| db_write_statements | 84 | 64 | -20 | -23.81% |
| redis_commands_parent_and_task_bodies | 507 | 421 | -86 | -16.96% |
| queue_wait_p50_s | 5.35184 | 2.70903 | -2.64281 | -49.38% |
| queue_wait_empirical_p95_s | 124.974 | 124.974 | +0.000744343 | +0.00% |
| peak_pss_bytes | 3.81587e+08 | 3.83853e+08 | +2.26509e+06 | +0.59% |
| peak_uss_bytes | 3.21884e+08 | 3.23908e+08 | +2.02342e+06 | +0.63% |
| container_memory_peak_cumulative_bytes | 4.32583e+08 | 4.11611e+08 | -2.09715e+07 | -4.85% |
