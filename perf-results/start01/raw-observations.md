# Raw startup observations

All times are seconds. These are baseline conditions, not before/after optimization deltas.
Lower latency, CPU, bytes and peak memory are better for an equivalent workload. No tail percentiles are estimated.

| Sample | Healthy | Usable | CPU | Peak MiB | Disk read bytes | Disk write bytes |
|---|---:|---:|---:|---:|---:|---:|
| baseline-large-unverified-cold-0 | 29.678573 | 38.143215 | 38.435062 | 1040.992 | 656121856 | 10006528 |
| baseline-large-unverified-cold-1 | 21.754016 | 30.068381 | 33.277331 | 1146.184 | 478474240 | 18882560 |
| baseline-large-unverified-cold-2 | 27.720284 | 53.814919 | 62.138196 | 1130.762 | 470335488 | 20246528 |
| baseline-large-verified-cold-0 | 20.255471 | 36.242257 | 37.073572 | 1150.129 | 475852800 | 17924096 |
| baseline-large-verified-cold-1 | 18.341301 | 25.664944 | 27.206565 | 1136.266 | 465723392 | 8118272 |
| baseline-large-verified-cold-2 | 19.679842 | 24.998203 | 27.158186 | 1130.430 | 464883712 | 8118272 |
| baseline-small-unverified-cold-0 | 32.353273 | 33.913487 | 31.243023 | 569.750 | 32759808 | 8335360 |
| baseline-small-unverified-cold-1 | 28.995984 | 30.033233 | 27.817356 | 575.738 | 54562816 | 19607552 |
| baseline-small-unverified-cold-2 | 46.558878 | 47.614954 | 37.728475 | 541.465 | 102191104 | 17084416 |
| baseline-small-verified-cold-0 | 67.417137 | 68.875884 | 49.370070 | 562.906 | 28614656 | 14163968 |
| baseline-small-verified-cold-1 | 22.862578 | 23.667280 | 27.931505 | 544.230 | 7499776 | 8118272 |
| baseline-small-verified-cold-2 | 18.522947 | 19.291832 | 22.855999 | 552.613 | 17252352 | 8118272 |

## Profiled integrity stages

`rchar` includes small instrumentation reads; physical `read_bytes` is reported separately.

| Sample | Stage | Wall s | CPU s | Logical bytes read | Physical bytes read |
|---|---|---:|---:|---:|---:|
| baseline-large-unverified-cold-0 | _skip_recently_verified | 0.021026 | 0.002196 | 103 | 0 |
| baseline-large-unverified-cold-0 | _warm_cache | 1.539341 | 0.949598 | 441847913 | 441847808 |
| baseline-large-unverified-cold-0 | _scan_and_publish_block | 4.514629 | 4.447234 | 1692913925 | 0 |
| baseline-large-unverified-cold-1 | _skip_recently_verified | 0.002147 | 0.000996 | 103 | 0 |
| baseline-large-unverified-cold-1 | _warm_cache | 0.908307 | 0.661303 | 441847913 | 441847808 |
| baseline-large-unverified-cold-1 | _scan_and_publish_block | 4.074805 | 4.037190 | 1692913925 | 0 |
| baseline-large-unverified-cold-2 | _skip_recently_verified | 0.003073 | 0.001963 | 103 | 0 |
| baseline-large-unverified-cold-2 | _warm_cache | 1.467877 | 0.596561 | 441847913 | 441847808 |
| baseline-large-unverified-cold-2 | _scan_and_publish_block | 2.602085 | 2.555205 | 1692913925 | 0 |
| baseline-large-verified-cold-0 | _skip_recently_verified | 0.026922 | 0.017303 | 291305 | 368640 |
| baseline-large-verified-cold-1 | _skip_recently_verified | 0.060732 | 0.036636 | 291305 | 368640 |
| baseline-large-verified-cold-2 | _skip_recently_verified | 0.132410 | 0.030926 | 291305 | 368640 |
| baseline-small-unverified-cold-0 | _skip_recently_verified | 0.005218 | 0.001598 | 103 | 0 |
| baseline-small-unverified-cold-0 | _warm_cache | 0.064745 | 0.026756 | 7639145 | 7639040 |
| baseline-small-unverified-cold-0 | _scan_and_publish_block | 0.486579 | 0.255053 | 22298882 | 0 |
| baseline-small-unverified-cold-1 | _skip_recently_verified | 0.003955 | 0.001045 | 103 | 0 |
| baseline-small-unverified-cold-1 | _warm_cache | 0.088301 | 0.065564 | 7639145 | 7639040 |
| baseline-small-unverified-cold-1 | _scan_and_publish_block | 0.144980 | 0.042805 | 22298882 | 0 |
| baseline-small-unverified-cold-2 | _skip_recently_verified | 0.002712 | 0.001387 | 103 | 0 |
| baseline-small-unverified-cold-2 | _warm_cache | 0.087446 | 0.064361 | 7639145 | 7639040 |
| baseline-small-unverified-cold-2 | _scan_and_publish_block | 0.126299 | 0.061402 | 22298882 | 0 |
| baseline-small-verified-cold-0 | _skip_recently_verified | 0.469261 | 0.083651 | 291305 | 368640 |
| baseline-small-verified-cold-1 | _skip_recently_verified | 0.038358 | 0.021687 | 291305 | 368640 |
| baseline-small-verified-cold-2 | _skip_recently_verified | 0.026189 | 0.017029 | 291305 | 368640 |

## Other startup stages

| Sample | Stage | Wall s | CPU s |
|---|---|---:|---:|
| baseline-large-unverified-cold-0 | Applying database migrations | 12.528250 | 10.568280 |
| baseline-large-unverified-cold-0 | Collecting static files | 2.036017 | 2.028516 |
| baseline-large-unverified-cold-0 | Fixing file ownership | 0.943967 | 0.539537 |
| baseline-large-unverified-cold-1 | Applying database migrations | 6.727175 | 6.349643 |
| baseline-large-unverified-cold-1 | Collecting static files | 2.091747 | 2.089159 |
| baseline-large-unverified-cold-1 | Fixing file ownership | 1.033467 | 0.596215 |
| baseline-large-unverified-cold-2 | Applying database migrations | 8.979522 | 8.174498 |
| baseline-large-unverified-cold-2 | Collecting static files | 1.555578 | 1.549361 |
| baseline-large-unverified-cold-2 | Fixing file ownership | 0.893486 | 0.537728 |
| baseline-large-verified-cold-0 | Applying database migrations | 7.477721 | 6.933541 |
| baseline-large-verified-cold-0 | Collecting static files | 2.029337 | 2.054807 |
| baseline-large-verified-cold-0 | Fixing file ownership | 2.169419 | 1.111115 |
| baseline-large-verified-cold-1 | Applying database migrations | 8.034115 | 7.539850 |
| baseline-large-verified-cold-1 | Collecting static files | 1.940590 | 1.928213 |
| baseline-large-verified-cold-1 | Fixing file ownership | 1.254123 | 0.676718 |
| baseline-large-verified-cold-2 | Applying database migrations | 8.146416 | 7.503909 |
| baseline-large-verified-cold-2 | Collecting static files | 2.280344 | 2.262566 |
| baseline-large-verified-cold-2 | Fixing file ownership | 1.593324 | 0.944084 |
| baseline-small-unverified-cold-0 | Applying database migrations | 16.761328 | 12.540169 |
| baseline-small-unverified-cold-0 | Collecting static files | 1.923071 | 1.863844 |
| baseline-small-unverified-cold-0 | Fixing file ownership | 2.658890 | 0.854613 |
| baseline-small-unverified-cold-1 | Applying database migrations | 9.477735 | 7.488945 |
| baseline-small-unverified-cold-1 | Collecting static files | 2.638145 | 2.132327 |
| baseline-small-unverified-cold-1 | Fixing file ownership | 3.828832 | 1.184106 |
| baseline-small-unverified-cold-2 | Applying database migrations | 20.049321 | 14.131258 |
| baseline-small-unverified-cold-2 | Collecting static files | 7.315691 | 3.795233 |
| baseline-small-unverified-cold-2 | Fixing file ownership | 2.429939 | 1.027185 |
| baseline-small-verified-cold-0 | Applying database migrations | 43.462480 | 28.909884 |
| baseline-small-verified-cold-0 | Collecting static files | 2.655635 | 2.601210 |
| baseline-small-verified-cold-0 | Fixing file ownership | 0.910409 | 0.551767 |
| baseline-small-verified-cold-1 | Applying database migrations | 9.353480 | 9.075724 |
| baseline-small-verified-cold-1 | Collecting static files | 2.194717 | 2.197564 |
| baseline-small-verified-cold-1 | Fixing file ownership | 1.626832 | 1.093162 |
| baseline-small-verified-cold-2 | Applying database migrations | 7.261314 | 6.589227 |
| baseline-small-verified-cold-2 | Collecting static files | 1.539296 | 1.546375 |
| baseline-small-verified-cold-2 | Fixing file ownership | 1.142696 | 0.704692 |

## Post-ready probes

Each value is the within-start median of ten sequential requests. Application is otherwise idle, host is shared/loaded.

| Sample | Library ms | Invalid-token webhook ms |
|---|---:|---:|
| baseline-large-unverified-cold-0 | 998.257 | 4.859 |
| baseline-large-unverified-cold-1 | 1717.706 | 7.924 |
| baseline-large-unverified-cold-2 | 748.627 | 3.530 |
| baseline-large-verified-cold-0 | 1507.198 | 3.391 |
| baseline-large-verified-cold-1 | 518.238 | 3.349 |
| baseline-large-verified-cold-2 | 984.558 | 3.411 |
| baseline-small-unverified-cold-0 | 211.995 | 4.972 |
| baseline-small-unverified-cold-1 | 327.254 | 7.382 |
| baseline-small-unverified-cold-2 | 330.481 | 10.005 |
| baseline-small-verified-cold-0 | 211.343 | 3.921 |
| baseline-small-verified-cold-1 | 209.099 | 6.948 |
| baseline-small-verified-cold-2 | 135.544 | 2.520 |
