# Before/after cohort medians

Lower is better for every metric below. Delta = changed minus baseline; percent = 100 × delta / baseline. Ordered cold cohorts are confounded by shared-host load. Warm trials alternate versions; trial zero is excluded.

| Size / verification / cache | Metric | Baseline | Changed | Absolute delta | Percent |
|---|---|---:|---:|---:|---:|
| large / unverified / cold | healthy_s | 99.795 | 27.924 | -71.871 | -72.02% |
| large / unverified / cold | usable_s | 118.582 | 41.048 | -77.534 | -65.38% |
| large / unverified / cold | cpu_s | 98.831 | 38.415 | -60.416 | -61.13% |
| large / unverified / cold | cpu_to_healthy_s | 82.808 | 29.744 | -53.064 | -64.08% |
| large / unverified / cold | peak_mib | 1136.391 | 972.234 | -164.156 | -14.45% |
| large / unverified / cold | peak_to_healthy_mib | 658.156 | 779.562 | +121.406 | +18.45% |
| large / unverified / cold | disk_read_bytes | 1990492160.000 | 1086443520.000 | -904048640.000 | -45.42% |
| large / unverified / cold | disk_write_bytes | 20242432.000 | 11563008.000 | -8679424.000 | -42.88% |
| large / unverified / cold | disk_io_bytes | 2010734592.000 | 1098575872.000 | -912158720.000 | -45.36% |
| large / unverified / cold | library_median_ms | 3772.436 | 2273.056 | -1499.380 | -39.75% |
| large / unverified / cold | webhook_median_ms | 13.597 | 7.185 | -6.411 | -47.15% |
| large / verified / cold | healthy_s | 38.325 | 23.392 | -14.932 | -38.96% |
| large / verified / cold | usable_s | 55.363 | 36.669 | -18.694 | -33.77% |
| large / verified / cold | cpu_s | 53.279 | 38.966 | -14.313 | -26.86% |
| large / verified / cold | cpu_to_healthy_s | 40.928 | 28.050 | -12.878 | -31.47% |
| large / verified / cold | peak_mib | 1066.352 | 1044.992 | -21.359 | -2.00% |
| large / verified / cold | peak_to_healthy_mib | 514.852 | 539.109 | +24.258 | +4.71% |
| large / verified / cold | disk_read_bytes | 671629312.000 | 807321600.000 | +135692288.000 | +20.20% |
| large / verified / cold | disk_write_bytes | 19623936.000 | 11354112.000 | -8269824.000 | -42.14% |
| large / verified / cold | disk_io_bytes | 690495488.000 | 818675712.000 | +128180224.000 | +18.56% |
| large / verified / cold | library_median_ms | 3584.725 | 2501.186 | -1083.539 | -30.23% |
| large / verified / cold | webhook_median_ms | 18.586 | 7.858 | -10.727 | -57.72% |
| small / unverified / cold | healthy_s | 34.923 | 42.473 | +7.551 | +21.62% |
| small / unverified / cold | usable_s | 36.748 | 45.869 | +9.120 | +24.82% |
| small / unverified / cold | cpu_s | 40.471 | 40.887 | +0.416 | +1.03% |
| small / unverified / cold | cpu_to_healthy_s | 36.818 | 37.786 | +0.968 | +2.63% |
| small / unverified / cold | peak_mib | 556.188 | 553.508 | -2.680 | -0.48% |
| small / unverified / cold | peak_to_healthy_mib | 512.863 | 508.492 | -4.371 | -0.85% |
| small / unverified / cold | disk_read_bytes | 42733568.000 | 46006272.000 | +3272704.000 | +7.66% |
| small / unverified / cold | disk_write_bytes | 19202048.000 | 11890688.000 | -7311360.000 | -38.08% |
| small / unverified / cold | disk_io_bytes | 61935616.000 | 57896960.000 | -4038656.000 | -6.52% |
| small / unverified / cold | library_median_ms | 443.493 | 470.234 | +26.741 | +6.03% |
| small / unverified / cold | webhook_median_ms | 16.842 | 8.374 | -8.469 | -50.28% |
| small / verified / cold | healthy_s | 65.886 | 41.973 | -23.913 | -36.29% |
| small / verified / cold | usable_s | 67.125 | 43.979 | -23.145 | -34.48% |
| small / verified / cold | cpu_s | 57.206 | 41.039 | -16.167 | -28.26% |
| small / verified / cold | cpu_to_healthy_s | 56.374 | 39.848 | -16.526 | -29.32% |
| small / verified / cold | peak_mib | 555.285 | 567.633 | +12.348 | +2.22% |
| small / verified / cold | peak_to_healthy_mib | 527.219 | 522.781 | -4.438 | -0.84% |
| small / verified / cold | disk_read_bytes | 120475648.000 | 79953920.000 | -40521728.000 | -33.63% |
| small / verified / cold | disk_write_bytes | 20512768.000 | 8138752.000 | -12374016.000 | -60.32% |
| small / verified / cold | disk_io_bytes | 141549568.000 | 88092672.000 | -53456896.000 | -37.77% |
| small / verified / cold | library_median_ms | 378.851 | 308.215 | -70.636 | -18.64% |
| small / verified / cold | webhook_median_ms | 13.848 | 6.395 | -7.453 | -53.82% |
| small / verified / warm | healthy_s | 40.776 | 27.809 | -12.967 | -31.80% |
| small / verified / warm | usable_s | 42.675 | 29.299 | -13.376 | -31.34% |
| small / verified / warm | cpu_s | 36.296 | 29.276 | -7.020 | -19.34% |
| small / verified / warm | cpu_to_healthy_s | 34.227 | 27.400 | -6.828 | -19.95% |
| small / verified / warm | peak_mib | 558.781 | 543.230 | -15.551 | -2.78% |
| small / verified / warm | peak_to_healthy_mib | 492.730 | 518.570 | +25.840 | +5.24% |
| small / verified / warm | disk_read_bytes | 71716864.000 | 44331008.000 | -27385856.000 | -38.19% |
| small / verified / warm | disk_write_bytes | 16932864.000 | 10792960.000 | -6139904.000 | -36.26% |
| small / verified / warm | disk_io_bytes | 87515136.000 | 53227520.000 | -34287616.000 | -39.18% |
| small / verified / warm | library_median_ms | 469.588 | 291.814 | -177.773 | -37.86% |
| small / verified / warm | webhook_median_ms | 10.523 | 5.419 | -5.104 | -48.50% |

## Alternating warm paired differences

Pairs match trial indices; version order alternates. Positive means worse. Five pairs provide weak statistical resolution; randomization also assumes the within-pair host drift is exchangeable, which shared-host load can violate.

| Metric | Raw changed-minus-baseline differences | Median difference |
|---|---|---:|
| healthy_s | -10.699, +7.946, -15.003, -22.140, -0.346 | -10.699 |
| usable_s | -10.766, +7.611, -16.594, -20.878, -0.542 | -10.766 |
| cpu_s | -6.931, +7.340, -8.869, -14.833, +0.799 | -6.931 |
| peak_mib | +23.488, -28.125, +29.012, -41.168, -15.551 | -15.551 |
| library_median_ms | -122.956, +1.409, -671.226, -32.118, -212.039 | -122.956 |
| webhook_median_ms | +1.367, -2.745, -40.417, +0.804, -5.373 | -2.745 |
| queue_roundtrip_ms | +243.866, -267.274, -124.543, -38.096, -218.923 | -124.543 |
