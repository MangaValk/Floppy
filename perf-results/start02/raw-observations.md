# Raw startup observations

All times are seconds. Both versions use the same controlled workload; see comparison.md for cohort deltas.
Lower latency, CPU, bytes and peak memory are better for an equivalent workload. No tail percentiles are estimated.

| Sample | Healthy | Usable | CPU | Peak MiB | Disk read bytes | Disk write bytes |
|---|---:|---:|---:|---:|---:|---:|
| baseline-large-unverified-cold-0 | 101.024319 | 118.582032 | 98.831300 | 1136.391 | 571203584 | 21061632 |
| baseline-large-unverified-cold-1 | 99.794659 | 136.954636 | 118.698253 | 1137.262 | 2902278144 | 20242432 |
| baseline-large-unverified-cold-2 | 66.155796 | 92.940637 | 74.502633 | 1048.664 | 1990492160 | 20242432 |
| baseline-large-verified-cold-0 | 29.693001 | 45.183952 | 44.594076 | 1066.352 | 671629312 | 18866176 |
| baseline-large-verified-cold-1 | 38.324621 | 55.362947 | 53.279207 | 1172.438 | 588533760 | 20226048 |
| baseline-large-verified-cold-2 | 48.427375 | 65.073599 | 59.363853 | 1044.473 | 684707840 | 19623936 |
| baseline-small-unverified-cold-0 | 34.922711 | 36.748253 | 47.098622 | 571.762 | 111382528 | 19955712 |
| baseline-small-unverified-cold-1 | 31.040870 | 33.329832 | 40.470743 | 556.188 | 34729984 | 18878464 |
| baseline-small-unverified-cold-2 | 35.418646 | 37.353806 | 38.437231 | 533.328 | 42733568 | 19202048 |
| baseline-small-verified-cold-0 | 42.347568 | 43.618668 | 45.631634 | 556.801 | 93786112 | 20512768 |
| baseline-small-verified-cold-1 | 65.885890 | 67.124661 | 57.206039 | 547.441 | 121569280 | 19980288 |
| baseline-small-verified-cold-2 | 72.854253 | 76.716318 | 65.535894 | 555.285 | 120475648 | 22155264 |
| baseline-small-verified-warm-0 | 25.758000 | 26.681541 | 30.369075 | 549.547 | 74444800 | 8118272 |
| baseline-small-verified-warm-1 | 36.015455 | 37.828426 | 35.353552 | 530.250 | 68788224 | 18726912 |
| baseline-small-verified-warm-2 | 33.404979 | 35.093429 | 34.305347 | 581.660 | 68575232 | 18898944 |
| baseline-small-verified-warm-3 | 42.812066 | 45.892558 | 38.145464 | 456.973 | 85983232 | 16932864 |
| baseline-small-verified-warm-4 | 46.312502 | 47.740793 | 40.605623 | 575.227 | 79314944 | 9154560 |
| baseline-small-verified-warm-5 | 40.775903 | 42.674996 | 36.295752 | 558.781 | 71716864 | 12943360 |
| changed-custom-uid-small-verified-cold-0 | 43.415437 | 45.867193 | 39.850292 | 553.816 | 75485184 | 19812352 |
| changed-large-unverified-cold-0 | 46.150303 | 66.631451 | 59.609301 | 972.234 | 1086443520 | 12132352 |
| changed-large-unverified-cold-1 | 27.923786 | 41.047719 | 38.415409 | 970.984 | 1082855424 | 8876032 |
| changed-large-unverified-cold-2 | 26.778596 | 36.977306 | 38.190850 | 1028.102 | 1089495040 | 11563008 |
| changed-large-verified-cold-0 | 25.925464 | 36.669339 | 38.965910 | 1044.992 | 726880256 | 11517952 |
| changed-large-verified-cold-1 | 23.392283 | 33.764200 | 34.266314 | 871.621 | 1354334208 | 10792960 |
| changed-large-verified-cold-2 | 22.634646 | 38.707076 | 46.280045 | 1170.734 | 807321600 | 11354112 |
| changed-small-unverified-cold-0 | 42.473312 | 45.965899 | 42.479720 | 563.426 | 34480128 | 13549568 |
| changed-small-unverified-cold-1 | 44.449022 | 45.868532 | 40.886874 | 527.660 | 46006272 | 11890688 |
| changed-small-unverified-cold-2 | 35.206562 | 36.754947 | 38.052847 | 553.508 | 72269824 | 10649600 |
| changed-small-verified-cold-0 | 41.973283 | 43.979201 | 41.038569 | 570.035 | 79953920 | 8138752 |
| changed-small-verified-cold-1 | 47.322568 | 48.875758 | 45.242205 | 539.918 | 87638016 | 10395648 |
| changed-small-verified-cold-2 | 32.083598 | 34.302415 | 34.348259 | 567.633 | 63668224 | 6189056 |
| changed-small-verified-warm-0 | 25.165360 | 26.314744 | 24.681618 | 579.520 | 56913920 | 11874304 |
| changed-small-verified-warm-1 | 25.316682 | 27.062781 | 28.422772 | 553.738 | 38584320 | 10792960 |
| changed-small-verified-warm-2 | 41.350560 | 42.703969 | 41.645390 | 553.535 | 77344768 | 3969024 |
| changed-small-verified-warm-3 | 27.809085 | 29.298870 | 29.275970 | 485.984 | 21147648 | 10825728 |
| changed-small-verified-warm-4 | 24.172859 | 26.863107 | 25.773069 | 534.059 | 52420608 | 10792960 |
| changed-small-verified-warm-5 | 40.429928 | 42.132603 | 37.094617 | 543.230 | 44331008 | 8896512 |

## Profiled integrity stages

`rchar` includes small instrumentation reads; physical `read_bytes` is reported separately.

| Sample | Stage | Wall s | CPU s | Logical bytes read | Physical bytes read |
|---|---|---:|---:|---:|---:|
| baseline-large-unverified-cold-0 | _skip_recently_verified | 0.026571 | 0.009655 | 103 | 0 |
| baseline-large-unverified-cold-0 | _warm_cache | 2.603960 | 1.071651 | 441831529 | 441831424 |
| baseline-large-unverified-cold-0 | _scan_and_publish_block | 8.104694 | 6.705956 | 1692684549 | 659456 |
| baseline-large-unverified-cold-1 | _skip_recently_verified | 0.056634 | 0.006805 | 109 | 4096 |
| baseline-large-unverified-cold-1 | _warm_cache | 1.348770 | 0.892715 | 441831535 | 441831424 |
| baseline-large-unverified-cold-1 | _scan_and_publish_block | 13.091460 | 5.735517 | 1692684549 | 1324802048 |
| baseline-large-unverified-cold-2 | _skip_recently_verified | 0.004330 | 0.001031 | 106 | 0 |
| baseline-large-unverified-cold-2 | _warm_cache | 1.501203 | 0.833380 | 441831532 | 441831424 |
| baseline-large-unverified-cold-2 | _scan_and_publish_block | 16.227451 | 7.724330 | 1692684549 | 426545152 |
| baseline-large-verified-cold-0 | _skip_recently_verified | 0.092260 | 0.027890 | 291309 | 372736 |
| baseline-large-verified-cold-1 | _skip_recently_verified | 0.090555 | 0.031300 | 291311 | 368640 |
| baseline-large-verified-cold-2 | _skip_recently_verified | 0.218663 | 0.034967 | 291305 | 368640 |
| baseline-small-unverified-cold-0 | _skip_recently_verified | 0.001919 | 0.000993 | 103 | 0 |
| baseline-small-unverified-cold-0 | _warm_cache | 0.040711 | 0.030942 | 7618665 | 7618560 |
| baseline-small-unverified-cold-0 | _scan_and_publish_block | 0.048858 | 0.039703 | 22057218 | 0 |
| baseline-small-unverified-cold-1 | _skip_recently_verified | 0.005148 | 0.002116 | 103 | 0 |
| baseline-small-unverified-cold-1 | _warm_cache | 0.057734 | 0.040363 | 7618665 | 7618560 |
| baseline-small-unverified-cold-1 | _scan_and_publish_block | 0.125634 | 0.076590 | 22057218 | 0 |
| baseline-small-unverified-cold-2 | _skip_recently_verified | 0.013643 | 0.003406 | 103 | 0 |
| baseline-small-unverified-cold-2 | _warm_cache | 0.112445 | 0.050106 | 7618665 | 7618560 |
| baseline-small-unverified-cold-2 | _scan_and_publish_block | 0.182449 | 0.099709 | 22057218 | 0 |
| baseline-small-verified-cold-0 | _skip_recently_verified | 0.078869 | 0.025465 | 291305 | 368640 |
| baseline-small-verified-cold-1 | _skip_recently_verified | 0.605059 | 0.051250 | 291305 | 368640 |
| baseline-small-verified-cold-2 | _skip_recently_verified | 0.137744 | 0.024683 | 291305 | 372736 |
| baseline-small-verified-warm-0 | _skip_recently_verified | 0.015257 | 0.010319 | 291305 | 0 |
| baseline-small-verified-warm-1 | _skip_recently_verified | 0.229328 | 0.041517 | 291305 | 368640 |
| baseline-small-verified-warm-2 | _skip_recently_verified | 0.174813 | 0.031721 | 291305 | 1175552 |
| baseline-small-verified-warm-3 | _skip_recently_verified | 0.225888 | 0.031300 | 291305 | 372736 |
| baseline-small-verified-warm-4 | _skip_recently_verified | 0.081605 | 0.023381 | 291305 | 368640 |
| baseline-small-verified-warm-5 | _skip_recently_verified | 0.232340 | 0.040252 | 291305 | 368640 |
| changed-custom-uid-small-verified-cold-0 | _skip_recently_verified | 0.134389 | 0.024068 | 291305 | 372736 |
| changed-large-unverified-cold-0 | _skip_recently_verified | 0.003311 | 0.001198 | 103 | 0 |
| changed-large-unverified-cold-0 | _warm_cache | 1.053781 | 0.633903 | 441831529 | 441831424 |
| changed-large-unverified-cold-0 | _scan_and_publish_block | 6.542959 | 4.696917 | 1692684549 | 102490112 |
| changed-large-unverified-cold-1 | _skip_recently_verified | 0.002325 | 0.000887 | 107 | 0 |
| changed-large-unverified-cold-1 | _warm_cache | 0.785289 | 0.561149 | 441831533 | 441831424 |
| changed-large-unverified-cold-1 | _scan_and_publish_block | 4.720066 | 4.031532 | 1692684549 | 33013760 |
| changed-large-unverified-cold-2 | _skip_recently_verified | 0.004510 | 0.001505 | 103 | 0 |
| changed-large-unverified-cold-2 | _warm_cache | 0.749518 | 0.486038 | 441831529 | 441831424 |
| changed-large-unverified-cold-2 | _scan_and_publish_block | 3.848266 | 3.246807 | 1692684549 | 53301248 |
| changed-large-verified-cold-0 | _skip_recently_verified | 0.061993 | 0.020732 | 291305 | 368640 |
| changed-large-verified-cold-1 | _skip_recently_verified | 0.117964 | 0.034194 | 291309 | 1216512 |
| changed-large-verified-cold-2 | _skip_recently_verified | 0.098425 | 0.028454 | 291305 | 368640 |
| changed-small-unverified-cold-0 | _skip_recently_verified | 0.095841 | 0.005169 | 108 | 0 |
| changed-small-unverified-cold-0 | _warm_cache | 0.125834 | 0.028698 | 7618670 | 7618560 |
| changed-small-unverified-cold-0 | _scan_and_publish_block | 0.304507 | 0.131751 | 22057218 | 0 |
| changed-small-unverified-cold-1 | _skip_recently_verified | 0.008269 | 0.001346 | 103 | 0 |
| changed-small-unverified-cold-1 | _warm_cache | 0.048632 | 0.034795 | 7618665 | 7618560 |
| changed-small-unverified-cold-1 | _scan_and_publish_block | 0.070961 | 0.041844 | 22057218 | 0 |
| changed-small-unverified-cold-2 | _skip_recently_verified | 0.006851 | 0.001576 | 103 | 0 |
| changed-small-unverified-cold-2 | _warm_cache | 0.074810 | 0.043427 | 7618665 | 7618560 |
| changed-small-unverified-cold-2 | _scan_and_publish_block | 0.046972 | 0.030064 | 22057218 | 0 |
| changed-small-verified-cold-0 | _skip_recently_verified | 0.106550 | 0.030557 | 291305 | 372736 |
| changed-small-verified-cold-1 | _skip_recently_verified | 0.093097 | 0.034639 | 291310 | 372736 |
| changed-small-verified-cold-2 | _skip_recently_verified | 0.152466 | 0.031804 | 291310 | 372736 |
| changed-small-verified-warm-0 | _skip_recently_verified | 0.051721 | 0.014309 | 291305 | 0 |
| changed-small-verified-warm-1 | _skip_recently_verified | 0.063793 | 0.025083 | 291305 | 0 |
| changed-small-verified-warm-2 | _skip_recently_verified | 0.397837 | 0.071905 | 291305 | 368640 |
| changed-small-verified-warm-3 | _skip_recently_verified | 0.112649 | 0.013996 | 291305 | 0 |
| changed-small-verified-warm-4 | _skip_recently_verified | 0.048506 | 0.011955 | 291305 | 0 |
| changed-small-verified-warm-5 | _skip_recently_verified | 0.054106 | 0.012341 | 291305 | 0 |

## Other startup stages

| Sample | Stage | Wall s | CPU s | Block read bytes | Block write bytes |
|---|---|---:|---:|---:|---:|
| baseline-large-unverified-cold-0 | Applying database migrations | 38.286428 | 24.567880 | 53268480 | 8826880 |
| baseline-large-unverified-cold-0 | Collecting static files | 6.510690 | 5.571164 | 335872 | 0 |
| baseline-large-unverified-cold-0 | Fixing file ownership | 9.365787 | 3.337722 | 8871936 | 8097792 |
| baseline-large-unverified-cold-1 | Applying database migrations | 29.638220 | 22.056358 | 55422976 | 3981312 |
| baseline-large-unverified-cold-1 | Collecting static files | 6.924818 | 4.854184 | 23977984 | 0 |
| baseline-large-unverified-cold-1 | Fixing file ownership | 6.088275 | 3.085817 | 8650752 | 8097792 |
| baseline-large-unverified-cold-2 | Applying database migrations | 22.299016 | 15.928091 | 58671104 | 417792 |
| baseline-large-unverified-cold-2 | Collecting static files | 5.068419 | 3.921134 | 21237760 | 10125312 |
| baseline-large-unverified-cold-2 | Fixing file ownership | 3.642817 | 1.564989 | 14598144 | 8097792 |
| baseline-large-verified-cold-0 | Applying database migrations | 11.423975 | 9.340728 | 40529920 | 0 |
| baseline-large-verified-cold-0 | Collecting static files | 4.080232 | 2.929632 | 27598848 | 10747904 |
| baseline-large-verified-cold-0 | Fixing file ownership | 2.240275 | 1.266235 | 8830976 | 8097792 |
| baseline-large-verified-cold-1 | Applying database migrations | 13.933977 | 11.121153 | 45588480 | 10780672 |
| baseline-large-verified-cold-1 | Collecting static files | 3.939924 | 2.738490 | 27516928 | 0 |
| baseline-large-verified-cold-1 | Fixing file ownership | 3.586466 | 1.802606 | 23601152 | 8097792 |
| baseline-large-verified-cold-2 | Applying database migrations | 15.733583 | 12.568750 | 43245568 | 9084928 |
| baseline-large-verified-cold-2 | Collecting static files | 7.987100 | 5.088434 | 16822272 | 0 |
| baseline-large-verified-cold-2 | Fixing file ownership | 6.273281 | 2.899288 | 8851456 | 8097792 |
| baseline-small-unverified-cold-0 | Applying database migrations | 11.410713 | 9.998257 | 32309248 | 0 |
| baseline-small-unverified-cold-0 | Collecting static files | 2.590711 | 2.443580 | 6119424 | 10747904 |
| baseline-small-unverified-cold-0 | Fixing file ownership | 1.854493 | 1.015402 | 9187328 | 8097792 |
| baseline-small-unverified-cold-1 | Applying database migrations | 12.841258 | 11.595966 | 9965568 | 10747904 |
| baseline-small-unverified-cold-1 | Collecting static files | 2.759971 | 2.704916 | 184320 | 0 |
| baseline-small-unverified-cold-1 | Fixing file ownership | 1.933616 | 0.958023 | 8302592 | 8097792 |
| baseline-small-unverified-cold-2 | Applying database migrations | 11.614719 | 10.067283 | 5697536 | 9990144 |
| baseline-small-unverified-cold-2 | Collecting static files | 2.825114 | 2.630189 | 180224 | 0 |
| baseline-small-unverified-cold-2 | Fixing file ownership | 2.470007 | 0.967882 | 5521408 | 8097792 |
| baseline-small-verified-cold-0 | Applying database migrations | 11.494887 | 9.912083 | 11259904 | 10747904 |
| baseline-small-verified-cold-0 | Collecting static files | 5.892517 | 4.264830 | 20459520 | 0 |
| baseline-small-verified-cold-0 | Fixing file ownership | 4.336566 | 1.805440 | 15962112 | 8097792 |
| baseline-small-verified-cold-1 | Applying database migrations | 22.681119 | 15.908621 | 20414464 | 10575872 |
| baseline-small-verified-cold-1 | Collecting static files | 13.178410 | 6.371180 | 19615744 | 0 |
| baseline-small-verified-cold-1 | Fixing file ownership | 4.983120 | 2.361762 | 8990720 | 8097792 |
| baseline-small-verified-cold-2 | Applying database migrations | 29.319826 | 18.289140 | 40824832 | 10780672 |
| baseline-small-verified-cold-2 | Collecting static files | 8.943909 | 5.100346 | 17453056 | 1220608 |
| baseline-small-verified-cold-2 | Fixing file ownership | 4.419897 | 2.248907 | 8757248 | 8097792 |
| baseline-small-verified-warm-0 | Applying database migrations | 8.208255 | 7.612301 | 25423872 | 0 |
| baseline-small-verified-warm-0 | Collecting static files | 1.992022 | 1.828146 | 10817536 | 0 |
| baseline-small-verified-warm-0 | Fixing file ownership | 1.171337 | 0.645495 | 9306112 | 8097792 |
| baseline-small-verified-warm-1 | Applying database migrations | 14.022602 | 10.582871 | 21635072 | 10608640 |
| baseline-small-verified-warm-1 | Collecting static files | 4.560363 | 3.256715 | 13467648 | 0 |
| baseline-small-verified-warm-1 | Fixing file ownership | 2.714904 | 1.241493 | 8749056 | 8097792 |
| baseline-small-verified-warm-2 | Applying database migrations | 12.985667 | 9.965777 | 16736256 | 10780672 |
| baseline-small-verified-warm-2 | Collecting static files | 3.886658 | 2.899553 | 15458304 | 0 |
| baseline-small-verified-warm-2 | Fixing file ownership | 2.928849 | 1.332722 | 10854400 | 8097792 |
| baseline-small-verified-warm-3 | Applying database migrations | 14.980713 | 9.875012 | 39297024 | 7974912 |
| baseline-small-verified-warm-3 | Collecting static files | 5.014437 | 3.235321 | 958464 | 0 |
| baseline-small-verified-warm-3 | Fixing file ownership | 3.772296 | 1.406614 | 8896512 | 8097792 |
| baseline-small-verified-warm-4 | Applying database migrations | 19.978590 | 12.909632 | 34439168 | 204800 |
| baseline-small-verified-warm-4 | Collecting static files | 4.781693 | 3.077228 | 7028736 | 0 |
| baseline-small-verified-warm-4 | Fixing file ownership | 3.989604 | 1.733367 | 8761344 | 8097792 |
| baseline-small-verified-warm-5 | Applying database migrations | 19.543978 | 12.897249 | 29974528 | 4825088 |
| baseline-small-verified-warm-5 | Collecting static files | 3.974363 | 2.990815 | 10756096 | 0 |
| baseline-small-verified-warm-5 | Fixing file ownership | 3.680271 | 1.563540 | 9707520 | 8097792 |
| changed-custom-uid-small-verified-cold-0 | Applying database migrations | 21.265591 | 13.356049 | 40157184 | 4186112 |
| changed-custom-uid-small-verified-cold-0 | Collecting static files | 0.451905 | 0.268495 | 405504 | 0 |
| changed-custom-uid-small-verified-cold-0 | Fixing file ownership | 4.162737 | 1.760325 | 8548352 | 8134656 |
| changed-large-unverified-cold-0 | Applying database migrations | 17.021294 | 12.458293 | 49979392 | 811008 |
| changed-large-unverified-cold-0 | Collecting static files | 1.011399 | 0.565293 | 536576 | 0 |
| changed-large-unverified-cold-0 | Fixing file ownership | 2.273290 | 1.484237 | 5521408 | 24576 |
| changed-large-unverified-cold-1 | Applying database migrations | 11.062626 | 9.090114 | 46731264 | 8093696 |
| changed-large-unverified-cold-1 | Collecting static files | 0.313680 | 0.209857 | 3092480 | 0 |
| changed-large-unverified-cold-1 | Fixing file ownership | 1.031385 | 0.820865 | 7102464 | 24576 |
| changed-large-unverified-cold-2 | Applying database migrations | 10.449001 | 8.802751 | 45936640 | 10780672 |
| changed-large-unverified-cold-2 | Collecting static files | 0.152000 | 0.134765 | 3125248 | 0 |
| changed-large-unverified-cold-2 | Fixing file ownership | 0.805782 | 0.690078 | 6111232 | 24576 |
| changed-large-verified-cold-0 | Applying database migrations | 12.364453 | 11.308080 | 19349504 | 0 |
| changed-large-verified-cold-0 | Collecting static files | 0.774846 | 0.676070 | 667648 | 10747904 |
| changed-large-verified-cold-0 | Fixing file ownership | 1.489520 | 1.345087 | 200704 | 24576 |
| changed-large-verified-cold-1 | Applying database migrations | 11.478326 | 9.575860 | 48361472 | 10747904 |
| changed-large-verified-cold-1 | Collecting static files | 0.246604 | 0.204739 | 573440 | 0 |
| changed-large-verified-cold-1 | Fixing file ownership | 0.901412 | 0.741091 | 5849088 | 24576 |
| changed-large-verified-cold-2 | Applying database migrations | 9.753037 | 8.864518 | 19206144 | 0 |
| changed-large-verified-cold-2 | Collecting static files | 0.210569 | 0.170941 | 4001792 | 0 |
| changed-large-verified-cold-2 | Fixing file ownership | 1.000861 | 0.823979 | 7655424 | 24576 |
| changed-small-unverified-cold-0 | Applying database migrations | 25.393472 | 16.368684 | 14307328 | 10747904 |
| changed-small-unverified-cold-0 | Collecting static files | 0.334852 | 0.219875 | 233472 | 0 |
| changed-small-unverified-cold-0 | Fixing file ownership | 1.498772 | 1.296357 | 397312 | 24576 |
| changed-small-unverified-cold-1 | Applying database migrations | 24.358513 | 15.989536 | 14655488 | 507904 |
| changed-small-unverified-cold-1 | Collecting static files | 0.349334 | 0.254845 | 348160 | 0 |
| changed-small-unverified-cold-1 | Fixing file ownership | 1.837757 | 1.428608 | 1540096 | 24576 |
| changed-small-unverified-cold-2 | Applying database migrations | 15.908095 | 11.897531 | 17461248 | 9510912 |
| changed-small-unverified-cold-2 | Collecting static files | 0.201792 | 0.172608 | 724992 | 0 |
| changed-small-unverified-cold-2 | Fixing file ownership | 1.160001 | 0.884975 | 2695168 | 24576 |
| changed-small-verified-cold-0 | Applying database migrations | 19.666437 | 13.353727 | 28278784 | 8093696 |
| changed-small-verified-cold-0 | Collecting static files | 0.422030 | 0.225643 | 425984 | 0 |
| changed-small-verified-cold-0 | Fixing file ownership | 1.338901 | 1.025378 | 483328 | 24576 |
| changed-small-verified-cold-1 | Applying database migrations | 22.159616 | 14.251711 | 32378880 | 4501504 |
| changed-small-verified-cold-1 | Collecting static files | 0.359716 | 0.230011 | 1392640 | 0 |
| changed-small-verified-cold-1 | Fixing file ownership | 1.491700 | 1.186585 | 1036288 | 24576 |
| changed-small-verified-cold-2 | Applying database migrations | 17.202836 | 12.017435 | 34762752 | 6144000 |
| changed-small-verified-cold-2 | Collecting static files | 0.508137 | 0.338340 | 471040 | 0 |
| changed-small-verified-cold-2 | Fixing file ownership | 0.910246 | 0.820580 | 360448 | 24576 |
| changed-small-verified-warm-0 | Applying database migrations | 11.419412 | 7.665834 | 19587072 | 0 |
| changed-small-verified-warm-0 | Collecting static files | 0.561859 | 0.252034 | 495616 | 0 |
| changed-small-verified-warm-0 | Fixing file ownership | 1.441704 | 0.986423 | 446464 | 10772480 |
| changed-small-verified-warm-1 | Applying database migrations | 12.711442 | 10.102389 | 10776576 | 10747904 |
| changed-small-verified-warm-1 | Collecting static files | 0.356553 | 0.284917 | 299008 | 0 |
| changed-small-verified-warm-1 | Fixing file ownership | 0.797178 | 0.703587 | 98304 | 24576 |
| changed-small-verified-warm-2 | Applying database migrations | 16.058466 | 11.165154 | 36417536 | 2064384 |
| changed-small-verified-warm-2 | Collecting static files | 0.455352 | 0.277953 | 503808 | 0 |
| changed-small-verified-warm-2 | Fixing file ownership | 1.257408 | 0.932473 | 1830912 | 24576 |
| changed-small-verified-warm-3 | Applying database migrations | 14.624258 | 10.467525 | 9797632 | 10780672 |
| changed-small-verified-warm-3 | Collecting static files | 0.226869 | 0.202686 | 155648 | 0 |
| changed-small-verified-warm-3 | Fixing file ownership | 1.305898 | 0.999575 | 69632 | 24576 |
| changed-small-verified-warm-4 | Applying database migrations | 10.930350 | 8.434371 | 18804736 | 0 |
| changed-small-verified-warm-4 | Collecting static files | 0.547258 | 0.309160 | 372736 | 0 |
| changed-small-verified-warm-4 | Fixing file ownership | 1.046067 | 0.715564 | 389120 | 10772480 |
| changed-small-verified-warm-5 | Applying database migrations | 18.198836 | 12.621664 | 10190848 | 7770112 |
| changed-small-verified-warm-5 | Collecting static files | 0.425918 | 0.294079 | 155648 | 0 |
| changed-small-verified-warm-5 | Fixing file ownership | 1.814839 | 1.179573 | 77824 | 24576 |

## Post-ready probes

Each value is the within-start median of ten sequential requests. Application is otherwise idle, host is shared/loaded.

| Sample | Library ms | Invalid-token webhook ms |
|---|---:|---:|
| baseline-large-unverified-cold-0 | 5351.881 | 13.597 |
| baseline-large-unverified-cold-1 | 3772.436 | 11.261 |
| baseline-large-unverified-cold-2 | 3388.325 | 14.374 |
| baseline-large-verified-cold-0 | 3584.725 | 9.710 |
| baseline-large-verified-cold-1 | 3197.317 | 18.586 |
| baseline-large-verified-cold-2 | 3593.847 | 21.063 |
| baseline-small-unverified-cold-0 | 443.493 | 10.109 |
| baseline-small-unverified-cold-1 | 338.825 | 16.842 |
| baseline-small-unverified-cold-2 | 620.960 | 20.922 |
| baseline-small-verified-cold-0 | 242.234 | 6.745 |
| baseline-small-verified-cold-1 | 378.851 | 13.848 |
| baseline-small-verified-cold-2 | 627.800 | 18.013 |
| baseline-small-verified-warm-0 | 219.734 | 6.737 |
| baseline-small-verified-warm-1 | 515.005 | 5.240 |
| baseline-small-verified-warm-2 | 359.092 | 10.523 |
| baseline-small-verified-warm-3 | 939.257 | 44.881 |
| baseline-small-verified-warm-4 | 323.932 | 4.283 |
| baseline-small-verified-warm-5 | 469.588 | 10.792 |
| changed-custom-uid-small-verified-cold-0 | 466.733 | 23.966 |
| changed-large-unverified-cold-0 | 2830.149 | 8.379 |
| changed-large-unverified-cold-1 | 2273.056 | 6.379 |
| changed-large-unverified-cold-2 | 1843.079 | 7.185 |
| changed-large-verified-cold-0 | 2096.887 | 7.858 |
| changed-large-verified-cold-1 | 2501.186 | 6.786 |
| changed-large-verified-cold-2 | 2974.983 | 7.921 |
| changed-small-unverified-cold-0 | 533.422 | 8.374 |
| changed-small-unverified-cold-1 | 292.261 | 12.278 |
| changed-small-unverified-cold-2 | 470.234 | 7.327 |
| changed-small-verified-cold-0 | 399.138 | 9.102 |
| changed-small-verified-cold-1 | 308.215 | 5.349 |
| changed-small-verified-cold-2 | 296.431 | 6.395 |
| changed-small-verified-warm-0 | 337.157 | 4.987 |
| changed-small-verified-warm-1 | 392.049 | 6.607 |
| changed-small-verified-warm-2 | 360.500 | 7.778 |
| changed-small-verified-warm-3 | 268.030 | 4.464 |
| changed-small-verified-warm-4 | 291.814 | 5.087 |
| changed-small-verified-warm-5 | 257.549 | 5.419 |
